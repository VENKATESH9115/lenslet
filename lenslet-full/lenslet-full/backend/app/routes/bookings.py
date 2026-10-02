import hashlib, hmac, re
from datetime import datetime
from typing import Literal
import httpx, psycopg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb
from ..config import S
from ..db import pool, q
from ..notify import notify
from ..security import need_user
from ..services import FLOW, audit, expire_unpaid, move, price, validate_window

router = APIRouter(prefix="/api", tags=["bookings"])


class Address(BaseModel):
    line1: str = Field(min_length=3, max_length=160)
    city: str = Field(min_length=2, max_length=60)
    pincode: str = Field(pattern=r"^\d{6}$")
    notes: str | None = Field(None, max_length=200)


class QuoteIn(BaseModel):
    equipment_ids: list[int] = Field(min_length=1, max_length=12)
    start: datetime
    end: datetime
    fulfilment: Literal["pickup", "home", "shoot"] = "pickup"
    address: Address | None = None


def _rows(ids):
    rows = q("select id,name,brand,price_day,deposit,status,category_id from equipment where id = any(%s)", (list(set(ids)),))
    if len(rows) != len(set(ids)):
        raise HTTPException(400, "One of the selected items no longer exists.")
    bad = [r["name"] for r in rows if r["status"] != "available"]
    if bad:
        raise HTTPException(409, f"{', '.join(bad)} is not available for rent right now.")
    return rows


def _prep(b: QuoteIn):
    if b.start.tzinfo is None or b.end.tzinfo is None:
        raise HTTPException(400, "Dates need a timezone.")
    validate_window(b.start, b.end)
    if b.fulfilment != "pickup" and not b.address:
        raise HTTPException(400, "Enter a delivery address with city and 6-digit pincode.")
    rows = _rows(b.equipment_ids)
    return rows, price(rows, b.start, b.end, b.fulfilment)


@router.post("/quote")
def quote(b: QuoteIn):
    rows, p = _prep(b)
    expire_unpaid()
    busy = q("select distinct bi.equipment_id from booking_items bi where bi.active and bi.equipment_id = any(%s) and bi.period && tstzrange(%s,%s,'[)')",
             ([r["id"] for r in rows], b.start, b.end))
    return {**p, "unavailable": [x["equipment_id"] for x in busy]}


def _alternatives(rows, start, end):
    out = {}
    for r in rows:
        out[r["id"]] = q("""select e.id,e.name,e.brand,e.price_day from equipment e
              where e.category_id=%s and e.id<>%s and e.status='available'
                and not exists (select 1 from booking_items bi where bi.equipment_id=e.id and bi.active and bi.period && tstzrange(%s,%s,'[)'))
              order by e.price_day limit 3""", (r["category_id"], r["id"], start, end))
    return out


@router.post("/bookings", status_code=201)
def create(b: QuoteIn, u=Depends(need_user)):
    rows, p = _prep(b)
    if not q("select 1 from kyc where user_id=%s", (u["id"],), one=True):
        raise HTTPException(403, detail={"code": "KYC_INCOMPLETE", "message": "Add your ID details before booking."})
    expire_unpaid()
    try:
        with pool.connection() as c:
            bk = c.execute("""insert into bookings(user_id,status,start_at,end_at,fulfilment,address,days,rental,discount,delivery_fee,tax,deposit,total)
                values (%s,'PAYMENT_PENDING',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id""",
                           (u["id"], b.start, b.end, b.fulfilment, Jsonb(b.address.model_dump()) if b.address else None,
                            p["days"], p["rental"], p["discount"], p["delivery"], p["tax"], p["deposit"], p["total"])).fetchone()
            code = f"CAM-{b.start.year}-{bk['id']:06d}"
            c.execute("update bookings set code=%s where id=%s", (code, bk["id"]))
            for r in rows:
                c.execute("insert into booking_items(booking_id,equipment_id,price_day,period) values (%s,%s,%s,tstzrange(%s,%s,'[)'))",
                          (bk["id"], r["id"], r["price_day"], b.start, b.end))
    except psycopg.errors.ExclusionViolation:
        raise HTTPException(409, detail={"code": "OVERLAP", "message": "Some of this gear was just booked for those dates.",
                                         "alternatives": _alternatives(rows, b.start, b.end)})
    audit(u["id"], "create", "booking", bk["id"], {"code": code})
    return {"id": bk["id"], "code": code, **p, "hold_minutes": S.hold_minutes}


LIST_SQL = """select b.*, coalesce((select json_agg(json_build_object('id',e.id,'name',e.name,'brand',e.brand,'slug',e.slug) order by e.id)
        from booking_items bi join equipment e on e.id=bi.equipment_id where bi.booking_id=b.id),'[]'::json) items,
      exists(select 1 from payments p where p.booking_id=b.id and p.status in ('paid','partially_refunded')) paid,
      coalesce((select sum(refunded) from payments p where p.booking_id=b.id),0) refunded
      from bookings b"""


def decorate(b):
    b["next"] = FLOW[b["status"]]
    return b


@router.get("/bookings")
def mine(u=Depends(need_user)):
    expire_unpaid()
    return [decorate(b) for b in q(LIST_SQL + " where b.user_id=%s order by b.id desc", (u["id"],))]


def _own(bid, u):
    b = q(LIST_SQL + " where b.id=%s", (bid,), one=True)
    if not b or (str(b["user_id"]) != str(u["id"]) and u["role"] != "admin"):
        raise HTTPException(404, "Booking not found.")
    return b


@router.get("/bookings/{bid}")
def one(bid: int, u=Depends(need_user)):
    return decorate(_own(bid, u))


@router.post("/bookings/{bid}/cancel")
def cancel(bid: int, u=Depends(need_user)):
    b = _own(bid, u)
    if b["status"] not in ("PAYMENT_PENDING", "CONFIRMED", "READY_FOR_PICKUP"):
        raise HTTPException(409, "This booking can no longer be cancelled online. Contact us.")
    move(bid, "CANCELLED", u["id"], "cancelled by customer")
    return {"status": "CANCELLED", "refund_pending": b["paid"]}


# ---- Razorpay -------------------------------------------------------------------------------
@router.post("/bookings/{bid}/pay")
def pay(bid: int, u=Depends(need_user)):
    b = _own(bid, u)
    if str(b["user_id"]) != str(u["id"]):
        raise HTTPException(403, "Only the customer can pay for this booking.")
    if b["status"] != "PAYMENT_PENDING":
        raise HTTPException(409, "This booking is not waiting for payment.")
    if not (S.rzp_id and S.rzp_secret):
        raise HTTPException(503, detail={"code": "PAYMENTS_NOT_CONFIGURED", "message": "Online payments are not set up on this server yet."})
    try:
        r = httpx.post("https://api.razorpay.com/v1/orders", auth=(S.rzp_id, S.rzp_secret), timeout=15,
                       json={"amount": b["total"], "currency": "INR", "receipt": b["code"]})
        r.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(502, "We could not reach the payment provider. Try again in a moment.")
    order = r.json()
    q("insert into payments(booking_id,provider,provider_order_id,amount,status) values (%s,'razorpay',%s,%s,'pending')",
      (bid, order["id"], b["total"]))
    return {"key_id": S.rzp_id, "order_id": order["id"], "amount": b["total"], "code": b["code"]}


class Verify(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/bookings/{bid}/verify")
def verify(bid: int, v: Verify, u=Depends(need_user)):
    b = _own(bid, u)
    p = q("select * from payments where booking_id=%s and provider_order_id=%s", (bid, v.razorpay_order_id), one=True)
    if not p:
        raise HTTPException(404, "No matching payment order.")
    expected = hmac.new(S.rzp_secret.encode(), f"{v.razorpay_order_id}|{v.razorpay_payment_id}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, v.razorpay_signature):
        q("update payments set status='failed' where id=%s", (p["id"],))
        raise HTTPException(400, "Payment could not be verified. You have not been charged for this booking.")
    q("update payments set status='paid', provider_payment_id=%s where id=%s", (v.razorpay_payment_id, p["id"]))
    if b["status"] == "PAYMENT_PENDING":
        move(bid, "CONFIRMED", u["id"], "razorpay payment verified")
    notify("payment_confirmation", bid, {"amount": b["total"]})
    return decorate(_own(bid, u))


# ---- KYC ------------------------------------------------------------------------------------
class KycIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    id_type: Literal["aadhaar", "passport", "driving_licence", "voter_id"]
    id_number: str = Field(min_length=4, max_length=24)


@router.get("/kyc")
def kyc_get(u=Depends(need_user)):
    return q("select full_name,id_type,id_last4,status,submitted_at from kyc where user_id=%s", (u["id"],), one=True) or {}


@router.put("/kyc")
def kyc_put(k: KycIn, u=Depends(need_user)):
    last4 = re.sub(r"\W", "", k.id_number)[-4:]     # the full ID number is never stored
    q("""insert into kyc(user_id,full_name,id_type,id_last4,status) values (%s,%s,%s,%s,'pending')
         on conflict (user_id) do update set full_name=excluded.full_name,id_type=excluded.id_type,id_last4=excluded.id_last4,status='pending',submitted_at=now(),reviewed_at=null""",
      (u["id"], k.full_name.strip(), k.id_type, last4))
    audit(u["id"], "kyc_submit", "kyc", u["id"])
    return kyc_get(u)


# ---- Invoice --------------------------------------------------------------------------------
@router.get("/bookings/{bid}/invoice", response_class=HTMLResponse)
def invoice(bid: int, u=Depends(need_user)):
    b = _own(bid, u)
    m = lambda p: f"₹{p/100:,.2f}"
    items = "".join(f"<tr><td>{i['brand']} {i['name']}</td></tr>" for i in b["items"])
    rows = [("Rental", b["rental"]), ("Discount", -b["discount"]), ("Delivery", b["delivery_fee"]), ("GST 18%", b["tax"]), ("Refundable security deposit", b["deposit"])]
    body = "".join(f"<tr><td>{k}</td><td style='text-align:right'>{m(v)}</td></tr>" for k, v in rows)
    return f"""<!doctype html><meta charset=utf-8><title>Invoice {b['code']}</title>
    <body style="font:15px Manrope,Arial;max-width:640px;margin:40px auto;color:#111">
    <h1>Lenslet</h1><p>Invoice for booking <b>{b['code']}</b><br>{b['start_at']:%d %b %Y %H:%M} to {b['end_at']:%d %b %Y %H:%M} ({b['days']} day(s))</p>
    <table width=100%>{items}</table><hr><table width=100%>{body}<tr><td><b>Total</b></td><td style='text-align:right'><b>{m(b['total'])}</b></td></tr></table>
    <p>Status: {b['status']}. {'Payment received.' if b['paid'] else 'Payment pending.'}</p><button onclick=print()>Print</button></body>"""
