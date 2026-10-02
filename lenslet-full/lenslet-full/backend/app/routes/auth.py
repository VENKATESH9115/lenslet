import re
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from authlib.integrations.starlette_client import OAuth
from ..config import S
from ..db import q
from ..security import check_password, current_user, hash_password, rate_limit, set_session
from ..services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

oauth = OAuth()
if S.google_id:
    oauth.register("google", client_id=S.google_id, client_secret=S.google_secret,
                   server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                   client_kwargs={"scope": "openid email profile"})


class Register(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(pattern=EMAIL, max_length=160)
    password: str = Field(min_length=8, max_length=128)


class Login(BaseModel):
    email: str = Field(pattern=EMAIL)
    password: str = Field(min_length=1, max_length=128)


def public(u):
    return {k: u[k] for k in ("id", "email", "name", "role", "avatar_url")} if u else None


@router.get("/providers")
def providers():
    return {"google": bool(S.google_id), "razorpay": bool(S.rzp_id and S.rzp_secret)}


@router.post("/register", status_code=201)
def register(b: Register, req: Request, resp: Response):
    rate_limit(req, "auth", 10)
    email = b.email.lower()
    if q("select 1 from users where lower(email)=%s", (email,), one=True):
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    role = "admin" if email in S.admin_emails else "customer"
    u = q("insert into users(email,name,password_hash,role) values (%s,%s,%s,%s) returning *",
          (email, b.name.strip(), hash_password(b.password), role), one=True)
    audit(u["id"], "register", "user", u["id"])
    set_session(resp, u["id"])
    return {"user": public(u)}


@router.post("/login")
def login(b: Login, req: Request, resp: Response):
    rate_limit(req, "auth", 10)
    u = q("select * from users where lower(email)=%s", (b.email.lower(),), one=True)
    if not u or not check_password(b.password, u["password_hash"]):
        if u and not u["password_hash"]:
            raise HTTPException(401, "This account uses Google sign-in. Continue with Google instead.")
        raise HTTPException(401, "Email or password is incorrect.")
    set_session(resp, u["id"])
    return {"user": public(u)}


@router.post("/logout", status_code=204)
def logout(resp: Response):
    resp.delete_cookie("lt", path="/")


@router.get("/me")
def me(req: Request):
    u = current_user(req)
    if not u:
        raise HTTPException(401, "Not signed in.")
    return {"user": public(u)}


@router.get("/google/login")
async def google_login(req: Request):
    if not S.google_id:
        raise HTTPException(501, "Google sign-in is not configured on this server.")
    return await oauth.google.authorize_redirect(req, f"{S.base_url}/api/auth/google/callback")


@router.get("/google/callback")
async def google_callback(req: Request):
    if not S.google_id:
        raise HTTPException(501, "Google sign-in is not configured on this server.")
    try:
        token = await oauth.google.authorize_access_token(req)
    except Exception:
        return RedirectResponse("/login.html?error=google")
    info = token.get("userinfo") or {}
    email = (info.get("email") or "").lower()
    if not email or not info.get("email_verified"):
        return RedirectResponse("/login.html?error=unverified")
    u = q("select * from users where google_sub=%s or lower(email)=%s", (info["sub"], email), one=True)
    if u:
        u = q("update users set google_sub=%s, avatar_url=coalesce(avatar_url,%s) where id=%s returning *",
              (info["sub"], info.get("picture"), u["id"]), one=True)
    else:
        role = "admin" if email in S.admin_emails else "customer"
        u = q("insert into users(email,name,google_sub,avatar_url,role) values (%s,%s,%s,%s,%s) returning *",
              (email, info.get("name") or email.split("@")[0], info["sub"], info.get("picture"), role), one=True)
        audit(u["id"], "register", "user", u["id"], {"via": "google"})
    r = RedirectResponse("/admin.html" if u["role"] == "admin" else "/account.html")
    set_session(r, u["id"])
    return r
