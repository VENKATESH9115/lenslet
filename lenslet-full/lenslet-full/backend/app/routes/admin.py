from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import httpx
from ..config import S
from ..db import q
from ..notify import notify
from ..security import need_admin
from ..services import FLOW, audit, expire_unpaid, move
from .bookings import LIST_SQL, decorate

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(need_admin)])


@router.get("/stats")
def stats():
    expire_unpaid()
    one = lambda sql: q(sql, one=True)["n"]
    return {
        "today_bookings": one("select count(*) n from bookings where start_at::date = current_date and status <> 'CANCELLED'"),
        "active_rentals": one("select count(*) n from bookings where status in ('RENTED','RETURN_PENDING')"),
        "today_returns": one("select count(*) n from bookings where end_at::date = current_date and status in ('RENTED','RETURN_PENDING')"),
        "pending_requests": one("select count(*) n from bookings where status = 'PAYMENT_PENDING'"),
        "revenue_30d": one("select coalesce(sum(amount - refunded),0) n from payments where status in ('paid','partially_refunded','refunded') and created_at > now() - interval '30 days'"),
        "deposits_held": one("select coalesce(sum(deposit),0) n from bookings where status in ('CONFIRMED','READY_FOR_PICKUP','RENTED','RETURN_PENDING','RETURNED','INSPECTION')"),
        "revenue_by_day": q("""select d::date as day, coalesce(sum(p.amount - p.refunded),0)::bigint as amount from generate_series(current_date - 13, current_date, '1 day') d
            left join payments p on p.created_at::date = d::date and p.status in ('paid','partially_refunded') group by 1 order by 1"""),
        "popular": q("select e.name, count(*) n from booking_items bi join equipment e on e.id=bi.equipment_id group by 1 order by 2 desc limit 5"),
        "upcoming_returns": q("select code,end_at,status from bookings where status in ('RENTED','RETURN_PENDING') order by end_at limit 6"),
        "refunds_pending": q("select b.code,b.id from bookings b where b.status='CANCELLED' and exists (select 1 from payments p where p.booking_id=b.id and p.status='paid')"),
    }


@router.get("/bookings")
def bookings(status: str | None = None):
    expire_unpaid()
    rows = q(LIST_SQL.replace("from bookings b", "from bookings b join users u on u.id=b.user_id", 1).replace(
        "select b.*,", "select b.*, u.name customer, u.email customer_email, (select status from kyc k where k.user_id=b.user_id) kyc_status,", 1)
        + " where (%s::text is null or b.status=%s) order by b.id desc limit 200", (status, status))
    return [decorate(b) for b in rows]


class Move(BaseModel):
    to: str


@router.post("/bookings/{bid}/transition")
def transition(bid: int, m: Move, a=Depends(need_admin)):
    if m.to not in FLOW:
        raise HTTPException(400, "Unknown status.")
    b = q(LIST_SQL + " where b.id=%s", (bid,), one=True)
    if not b:
        raise HTTPException(404, "Booking not found.")
    if m.to == "READY_FOR_PICKUP":
        k = q("select status from kyc where user_id=%s", (b["user_id"],), one=True)
        if not b["paid"] or not k or k["status"] != "approved":
            raise HTTPException(409, "Gear can be released only after payment is received and the customer's ID is approved.")
    if m.to == "COMPLETED" and not q("select 1 from inspections where booking_id=%s", (bid,), one=True):
        raise HTTPException(409, "Record the return inspection before completing the booking.")
    move(bid, m.to, a["id"])
    if m.to == "RETURN_PENDING":
        notify("return_reminder", bid)
    return decorate(q(LIST_SQL + " where b.id=%s", (bid,), one=True))


class Manual(BaseModel):
    method: Literal["cash", "upi", "card_at_counter", "bank_transfer"]


@router.post("/bookings/{bid}/record-payment")
def record_payment(bid: int, m: Manual, a=Depends(need_admin)):
    b = q("select total,status from bookings where id=%s", (bid,), one=True)
    if not b or b["status"] != "PAYMENT_PENDING":
        raise HTTPException(409, "Only bookings waiting for payment can take a payment.")
    q("insert into payments(booking_id,provider,method,amount,status) values (%s,'manual',%s,%s,'paid')", (bid, m.method, b["total"]))
    move(bid, "CONFIRMED", a["id"], f"manual payment: {m.method}")
    notify("payment_confirmation", bid, {"amount": b["total"]})
    return {"ok": True}


class Refund(BaseModel):
    amount: int = Field(gt=0, description="paise")


@router.post("/bookings/{bid}/refund")
def refund(bid: int, r: Refund, a=Depends(need_admin)):
    p = q("select * from payments where booking_id=%s and status in ('paid','partially_refunded') order by id desc limit 1", (bid,), one=True)
    if not p:
        raise HTTPException(409, "There is no paid payment to refund.")
    if r.amount > p["amount"] - p["refunded"]:
        raise HTTPException(400, "Refund is more than what was paid.")
    if p["provider"] == "razorpay" and p["provider_payment_id"]:
        try:
            httpx.post(f"https://api.razorpay.com/v1/payments/{p['provider_payment_id']}/refund", auth=(S.rzp_id, S.rzp_secret),
                       json={"amount": r.amount}, timeout=15).raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(502, "Razorpay did not accept the refund. Nothing was changed.")
    total = p["refunded"] + r.amount
    q("update payments set refunded=%s, status=%s where id=%s", (total, "refunded" if total >= p["amount"] else "partially_refunded", p["id"]))
    audit(a["id"], "refund", "booking", bid, {"amount": r.amount})
    notify("refund_processed", bid, {"amount": r.amount})
    return {"refunded": total}


class Inspection(BaseModel):
    condition_before: str = "excellent"
    condition_after: str = "excellent"
    damage: str = ""
    missing_items: str = ""
    late_hours: int = Field(0, ge=0)
    extra_charges: int = Field(0, ge=0)          # paise
    deposit_deductions: int = Field(0, ge=0)     # paise
    notes: str = ""


@router.post("/bookings/{bid}/inspection")
def inspection(bid: int, i: Inspection, a=Depends(need_admin)):
    b = q("select status,deposit from bookings where id=%s", (bid,), one=True)
    if not b or b["status"] not in ("RETURNED", "INSPECTION"):
        raise HTTPException(409, "Inspect after the gear has been returned.")
    refundable = max(0, b["deposit"] - i.deposit_deductions - i.extra_charges)
    q("""insert into inspections(booking_id,condition_before,condition_after,damage,missing_items,late_hours,extra_charges,deposit_deductions,deposit_refundable,notes,inspected_by)
         values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
      (bid, i.condition_before, i.condition_after, i.damage, i.missing_items, i.late_hours, i.extra_charges, i.deposit_deductions, refundable, i.notes, a["id"]))
    if i.damage.strip() or i.missing_items.strip():     # damaged gear leaves the rental pool until the owner clears it
        q("update equipment set status='maintenance', condition=%s where id in (select equipment_id from booking_items where booking_id=%s)", (i.condition_after, bid))
    else:
        q("update equipment set condition=%s where id in (select equipment_id from booking_items where booking_id=%s)", (i.condition_after, bid))
    if b["status"] == "RETURNED":
        move(bid, "INSPECTION", a["id"])
    if i.late_hours:
        notify("late_return", bid, {"late_hours": i.late_hours})
    return {"deposit_refundable": refundable}


# ---- Inventory ------------------------------------------------------------------------------
class EquipIn(BaseModel):
    category: str
    brand: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=2, max_length=80)
    short_spec: str = ""
    price_day: int = Field(gt=0)      # rupees
    deposit: int = Field(ge=0)        # rupees
    serial_no: str = ""


@router.get("/equipment")
def equipment():
    return q("select e.*, c.name category_name from equipment e join categories c on c.id=e.category_id order by e.status='archived', e.id")


@router.post("/equipment", status_code=201)
def add_equipment(e: EquipIn, a=Depends(need_admin)):
    import re
    c = q("select id from categories where slug=%s", (e.category,), one=True)
    if not c:
        raise HTTPException(400, "Unknown category.")
    slug = re.sub(r"[^a-z0-9]+", "-", e.name.lower()).strip("-")
    if q("select 1 from equipment where slug=%s", (slug,), one=True):
        slug += "-" + (e.serial_no.lower() or "2")
    row = q("""insert into equipment(slug,category_id,brand,name,short_spec,price_day,deposit,serial_no) values (%s,%s,%s,%s,%s,%s,%s,%s) returning id""",
            (slug, c["id"], e.brand, e.name, e.short_spec, e.price_day * 100, e.deposit * 100, e.serial_no), one=True)
    audit(a["id"], "create", "equipment", row["id"])
    return row


class EquipPatch(BaseModel):
    status: Literal["available", "maintenance", "unavailable", "archived"] | None = None
    price_day: int | None = Field(None, gt=0)
    deposit: int | None = Field(None, ge=0)
    condition: str | None = None


@router.patch("/equipment/{eid}")
def patch_equipment(eid: int, p: EquipPatch, a=Depends(need_admin)):
    if p.status in ("maintenance", "unavailable", "archived"):
        busy = q("select b.code from booking_items bi join bookings b on b.id=bi.booking_id where bi.equipment_id=%s and bi.active and upper(bi.period) > now() limit 1", (eid,), one=True)
        if busy:
            raise HTTPException(409, f"This item is part of booking {busy['code']}. Cancel or complete it first.")
    q("""update equipment set status=coalesce(%s,status), price_day=coalesce(%s,price_day), deposit=coalesce(%s,deposit), condition=coalesce(%s,condition) where id=%s""",
      (p.status, p.price_day and p.price_day * 100, p.deposit is not None and p.deposit * 100 or None, p.condition, eid))
    audit(a["id"], "update", "equipment", eid, p.model_dump(exclude_none=True))
    return {"ok": True}


# ---- Customers & KYC --------------------------------------------------------------------------
@router.get("/customers")
def customers():
    return q("""select u.id,u.name,u.email,u.created_at,k.status kyc_status,k.id_type,k.id_last4,k.full_name kyc_name,
                (select count(*) from bookings b where b.user_id=u.id) bookings
                from users u left join kyc k on k.user_id=u.id where u.role='customer' order by u.created_at desc limit 200""")


class KycReview(BaseModel):
    status: Literal["approved", "rejected"]


@router.post("/kyc/{uid}")
def review_kyc(uid: str, r: KycReview, a=Depends(need_admin)):
    q("update kyc set status=%s, reviewed_at=now() where user_id=%s", (r.status, uid))
    audit(a["id"], "kyc_" + r.status, "kyc", uid)
    return {"ok": True}
