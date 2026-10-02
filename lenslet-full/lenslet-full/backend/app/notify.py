"""Notification outbox. Add an email / WhatsApp / SMS sender by implementing Channel and registering it."""
from typing import Protocol
from psycopg.types.json import Jsonb
from .db import q


class Channel(Protocol):
    name: str
    def send(self, user: dict, kind: str, payload: dict) -> bool: ...


class ConsoleChannel:
    name = "email"
    def send(self, user, kind, payload):
        print(f"[notify:{self.name}] {kind} -> {user['email']} {payload}")
        return True


CHANNELS: dict[str, Channel] = {"email": ConsoleChannel()}   # e.g. CHANNELS["whatsapp"] = WhatsAppChannel()

KINDS = ("booking_confirmation", "payment_confirmation", "pickup_reminder", "return_reminder",
         "late_return", "booking_cancelled", "refund_processed")


def notify(kind: str, booking_id: int, payload: dict | None = None):
    b = q("select b.id,b.code,u.id uid,u.email,u.name from bookings b join users u on u.id=b.user_id where b.id=%s", (booking_id,), one=True)
    if not b:
        return
    data = {"code": b["code"], **(payload or {})}
    for name, ch in CHANNELS.items():
        ok = False
        try:
            ok = ch.send({"email": b["email"], "name": b["name"]}, kind, data)
        except Exception as e:  # never break a booking because a message failed
            print("notify failed", e)
        q("insert into notifications(user_id,booking_id,kind,channel,status,payload) values (%s,%s,%s,%s,%s,%s)",
          (b["uid"], booking_id, kind, name, "sent" if ok else "failed", Jsonb(data)))
