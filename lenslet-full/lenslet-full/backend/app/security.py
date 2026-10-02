import hashlib, hmac, os, time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, Request, Response
from .config import S
from .db import q

COOKIE = "lt"


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${h.hex()}"


def check_password(pw: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, salt, h = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


def set_session(resp: Response, user_id) -> None:
    exp = datetime.now(timezone.utc) + timedelta(days=7)
    token = jwt.encode({"sub": str(user_id), "exp": exp}, S.secret, algorithm="HS256")
    resp.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=S.cookie_secure, max_age=7 * 86400, path="/")


def current_user(req: Request):
    tok = req.cookies.get(COOKIE)
    if not tok:
        return None
    try:
        sub = jwt.decode(tok, S.secret, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        return None
    return q("select id,email,name,role,avatar_url,phone from users where id=%s", (sub,), one=True)


def need_user(u=Depends(current_user)):
    if not u:
        raise HTTPException(401, "Please sign in to continue.")
    return u


def need_admin(u=Depends(need_user)):
    if u["role"] != "admin":
        raise HTTPException(403, "Admin access only.")
    return u


_hits: dict = defaultdict(deque)


def rate_limit(req: Request, bucket: str, limit: int, per: int = 60):
    key = (bucket, req.client.host if req.client else "?")
    now, dq = time.time(), _hits[key]
    while dq and now - dq[0] > per:
        dq.popleft()
    if len(dq) >= limit:
        raise HTTPException(429, "Too many attempts. Wait a minute and try again.")
    dq.append(now)
