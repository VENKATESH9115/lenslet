# Lenslet: camera and gear rental platform (full stack)

Python (FastAPI) + PostgreSQL backend, with Google and email sign-in, live availability, booking lifecycle,
Razorpay payments, KYC, returns/inspection and an owner dashboard. The frontend is plain HTML/CSS/JS served by the same app.

## Run with Docker (easiest)
    cp .env.example .env
    docker compose up --build
    open http://localhost:8000

## Run without Docker
    # 1. PostgreSQL 14+ with a database and user
    createdb lenslet            # or: CREATE USER lenslet PASSWORD 'lenslet' SUPERUSER; CREATE DATABASE lenslet OWNER lenslet;
    # 2. Backend
    cp .env.example .env        # edit DATABASE_URL if needed
    cd backend
    python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload
    open http://localhost:8000
Tables and seed gear are created automatically on first start (`backend/app/schema.sql`).
API docs: http://localhost:8000/docs

## First steps
1. Put your email in `ADMIN_EMAILS` in `.env`, restart, then **create an account with that email**. It becomes the owner account and opens `/admin.html`.
2. Create a second (customer) account, add ID details in My account, and book gear from `/gear.html`.
3. As owner, record the payment (or set Razorpay keys), approve the customer's ID, then move the booking through
   ready for pickup, rented, return pending, returned, inspection and completed.

## Turning on Google sign-in
Google Cloud Console > APIs and Services > Credentials > OAuth client ID (Web). Add the redirect URI
`http://localhost:8000/api/auth/google/callback` (use your real domain and set `BASE_URL` and `COOKIE_SECURE=1` in production).
Put `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`.

## Turning on payments
Add `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`. The server creates the order and a booking is confirmed only after it
verifies Razorpay's signature. Without keys, the pay button explains that payments are off, and the owner can record
counter payments. Nothing is ever marked paid without proof.

## How double booking is prevented
`booking_items` has a PostgreSQL exclusion constraint (`btree_gist`): one unit cannot have two active, overlapping time ranges.
The database refuses the second booking even if two customers click at the same instant. The API then returns the free alternatives.
Unpaid bookings hold gear for 15 minutes, then release it.

## Layout
    backend/app/schema.sql      tables, constraints, seed data
    backend/app/services.py     lifecycle state machine, pricing
    backend/app/routes/         auth, catalog, bookings (+ payments, KYC, invoice), admin
    backend/app/notify.py       notification outbox; add email/WhatsApp/SMS channels here
    frontend/                   index, login, gear (catalogue + booking), account, admin

## Before going live
Set a long random `SECRET_KEY`, `COOKIE_SECURE=1`, HTTPS, and a real Razorpay webhook. Not built yet: booking extensions,
image uploads, reviews submission, coupons, scheduled reminder jobs, and a rate limiter that works across multiple servers.
