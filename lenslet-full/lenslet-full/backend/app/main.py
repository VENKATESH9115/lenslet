from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from .config import S
from . import db
from .routes import admin, auth, bookings, catalog


@asynccontextmanager
async def lifespan(app):
    db.init()
    yield
    db.pool.close()


app = FastAPI(title="Lenslet", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=S.secret, same_site="lax", https_only=S.cookie_secure)  # used only during the Google OAuth handshake
for r in (auth.router, catalog.router, bookings.router, admin.router):
    app.include_router(r)


@app.middleware("http")
async def headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    return resp


@app.exception_handler(Exception)
async def boom(request: Request, exc: Exception):
    print("ERROR", request.url.path, repr(exc))
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)


@app.get("/api/health")
def health():
    return {"ok": True}


app.mount("/public", StaticFiles(directory=S.frontend / "public"), name="public-assets")
app.mount("/", StaticFiles(directory=S.frontend, html=True), name="site")
