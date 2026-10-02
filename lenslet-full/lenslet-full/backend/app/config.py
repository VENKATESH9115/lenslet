import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")


class S:
    database_url = os.getenv("DATABASE_URL", "postgresql://lenslet:lenslet@localhost:5432/lenslet")
    secret = os.getenv("SECRET_KEY", "dev-secret-change-me")
    base_url = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
    cookie_secure = os.getenv("COOKIE_SECURE", "0") == "1"
    admin_emails = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
    google_id = os.getenv("GOOGLE_CLIENT_ID", "")
    google_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    rzp_id = os.getenv("RAZORPAY_KEY_ID", "")
    rzp_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    hold_minutes = 15          # unpaid bookings release the gear after this long
    gst = 0.18
    delivery_paise = {"pickup": 0, "home": 35000, "shoot": 60000}
    frontend = ROOT.parent / "frontend" if (ROOT.parent / "frontend").exists() else ROOT / "frontend"
