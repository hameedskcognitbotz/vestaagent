"""
VestaCode Auth Module
======================
Minimal JWT authentication using FastAPI's built-in security.
No OAuth — just register/login → JWT.  One-day implementation.

Usage:
    from backend.core.auth import get_current_user, router as auth_router
    app.include_router(auth_router, prefix="/auth")

    @app.get("/protected")
    async def protected(user: dict = Depends(get_current_user)):
        return {"user_id": user["user_id"]}
"""

import os
import sqlite3
import hashlib
import secrets
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

# ---------------------------------------------------------------------------
#  Config
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_EXPIRY_HOURS = 72
AUTH_DB_PATH = os.environ.get("VESTA_DB_PATH", "backend/data/projects.db")

security = HTTPBearer(auto_error=False)
router = APIRouter(tags=["auth"])


# ---------------------------------------------------------------------------
#  Simple JWT (no pyjwt dependency — just HMAC-SHA256 + base64)
# ---------------------------------------------------------------------------
import hmac
import base64


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def create_jwt(payload: dict) -> str:
    """Create a minimal JWT (HS256) with no external dependency."""
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload_b64 = _b64url(json.dumps(payload).encode())
    message = f"{header}.{payload_b64}"
    sig = hmac.new(JWT_SECRET.encode(), message.encode(), hashlib.sha256).digest()
    return f"{message}.{_b64url(sig)}"


def verify_jwt(token: str) -> Optional[dict]:
    """Verify a JWT; returns payload dict or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload_b64, sig_b64 = parts
        message = f"{header}.{payload_b64}"
        expected_sig = hmac.new(JWT_SECRET.encode(), message.encode(), hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        # Check expiry
        if payload.get("exp") and datetime.now(timezone.utc).timestamp() > payload["exp"]:
            return None
        return payload
    except Exception:
        return None


# ---------------------------------------------------------------------------
#  Password hashing (no bcrypt — stdlib only)
# ---------------------------------------------------------------------------
def _hash_pw(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return hashed, salt


# ---------------------------------------------------------------------------
#  SQLite user table
# ---------------------------------------------------------------------------
def _ensure_users_table():
    os.makedirs(os.path.dirname(AUTH_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     TEXT PRIMARY KEY,
            email       TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            pw_hash     TEXT NOT NULL,
            pw_salt     TEXT NOT NULL,
            created_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


_ensure_users_table()


def _get_user_by_email(email: str) -> Optional[dict]:
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
#  Request / Response models
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    name: str
    email: str


# ---------------------------------------------------------------------------
#  Routes
# ---------------------------------------------------------------------------
@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    if _get_user_by_email(req.email):
        raise HTTPException(status_code=409, detail="Email already registered.")

    user_id = secrets.token_hex(8)
    pw_hash, pw_salt = _hash_pw(req.password)
    now = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.execute(
        "INSERT INTO users (user_id, email, name, pw_hash, pw_salt, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, req.email, req.name, pw_hash, pw_salt, now),
    )
    conn.commit()
    conn.close()

    exp = (datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)).timestamp()
    token = create_jwt({"user_id": user_id, "email": req.email, "exp": exp})

    return AuthResponse(token=token, user_id=user_id, name=req.name, email=req.email)


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    user = _get_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    pw_hash, _ = _hash_pw(req.password, user["pw_salt"])
    if not hmac.compare_digest(pw_hash, user["pw_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    exp = (datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)).timestamp()
    token = create_jwt({"user_id": user["user_id"], "email": user["email"], "exp": exp})

    return AuthResponse(token=token, user_id=user["user_id"], name=user["name"], email=user["email"])


@router.get("/me")
async def me(user: dict = Depends(lambda creds=Depends(security): _require_auth(creds))):
    return {"user_id": user["user_id"], "email": user["email"]}


# ---------------------------------------------------------------------------
#  Dependency for protected routes
# ---------------------------------------------------------------------------
def _require_auth(credentials: Optional[HTTPAuthorizationCredentials]) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    payload = verify_jwt(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return payload


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """FastAPI dependency — inject into any route that needs auth."""
    return _require_auth(credentials)


def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[dict]:
    """Returns user dict if authenticated, None otherwise (for optional auth routes)."""
    if not credentials:
        return None
    payload = verify_jwt(credentials.credentials)
    return payload
