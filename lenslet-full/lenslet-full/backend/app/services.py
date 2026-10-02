import math
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from .config import S
from .db import pool, q
from .notify import notify

# Booking lifecycle. Anything not listed here is rejected.
FLOW = {
    "REQUESTED": ["PAYMENT_PENDING", "CANCELLED"],
    "PAYMENT_PENDING": ["CONFIRMED", "CANCELLED"],
    "CONFIRMED": ["READY_FOR_PICKUP", "CANCELLED"],
    "READY_FOR_PICKUP": ["RENTED", "CANCELLED"],
    "RENTED": ["RETURN_PENDING"],
    "RETURN_PENDING": ["RETURNED"],
    "RETURNED": ["INSPECTION"],
    "INSPECTION": ["COMPLETED"],
    "COMPLETED": [],
    "CANCELLED": [],
}
RELEASES_GEAR = {"CANCELLED", "COMPLETED"}
NOTIFY_ON = {"CONFIRMED": "booking_confirmation", "CANCELLED": "booking_cancelled"}


def audit(actor, action, entity, entity_id, detail=None):
    q("insert into audit_logs(actor_id,action,entity,entity_id,detail) values (%s,%s,%s,%s,%s)",
      (actor, action, entity, str(entity_id), Jsonb(detail or {})))


def move(booking_id: int, to: str, actor=None, note: str | None = None):
    """Single entry point for status changes. Locks the row, validates the transition, frees gear when due."""
    with pool.connection() as c:
        b = c.execute("select status from bookings where id=%s for update", (booking_id,)).fetchone()
        if not b:
            raise HTTPException(404, "Booking not found.")
        if to not in FLOW[b["status"]]:
            raise HTTPException(409, f"A booking in {b['status']} cannot move to {to}.")
        c.execute("update bookings set status=%s, updated_at=now() where id=%s", (to, booking_id))
        if to in RELEASES_GEAR:
            c.execute("update booking_items set active=false where booking_id=%s", (booking_id,))
    audit(actor, "status", "booking", booking_id, {"from": b["status"], "to": to, "note": note})
    if to in NOTIFY_ON:
        notify(NOTIFY_ON[to], booking_id)


def expire_unpaid():
    """Release gear held by bookings that were never paid."""
    q("""with x as (update bookings set status='CANCELLED', updated_at=now()
                   where status in ('REQUESTED','PAYMENT_PENDING') and created_at < now() - make_interval(mins => %s)
                   returning id)
         update booking_items set active=false where booking_id in (select id from x)""", (S.hold_minutes,))


def validate_window(start: datetime, end: datetime):
    now = datetime.now(timezone.utc)
    if start < now:
        raise HTTPException(400, "Pickup is in the past. Choose a later date and time.")
    if end <= start:
        raise HTTPException(400, "Return must be after pickup.")
    if end - start < timedelta(hours=4):
        raise HTTPException(400, "Minimum rental is 4 hours.")
    if end - start > timedelta(days=30):
        raise HTTPException(400, "Maximum rental is 30 days. Contact us for longer shoots.")


def price(rows: list[dict], start: datetime, end: datetime, fulfilment: str) -> dict:
    days = max(1, math.ceil((end - start).total_seconds() / 86400))
    rental = sum(r["price_day"] for r in rows) * days
    pct = (5 if days >= 3 else 0) + (5 if len(rows) >= 4 else 0)
    discount = rental * pct // 100
    delivery = S.delivery_paise[fulfilment]
    tax = round((rental - discount + delivery) * S.gst)
    deposit = sum(r["deposit"] for r in rows)
    return {"days": days, "rental": rental, "discount": discount, "discount_pct": pct, "delivery": delivery,
            "tax": tax, "deposit": deposit, "total": rental - discount + delivery + tax + deposit}
