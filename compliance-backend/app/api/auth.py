import os
import secrets
import uuid
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import RevokedToken, User
from app.services.email import send_temp_password_email
from app.services.password import hash_password, verify_password
from app.services.tokens import create_access_token, get_current_user, get_jti

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "session"
SECURE_COOKIE = os.getenv("ENVIRONMENT", "development") == "production"

# ---------------------------------------------------------------------------
# In-memory rate limiter — tracks failed login attempts per email address.
# Resets automatically after LOCKOUT_MINUTES. Survives for the process lifetime.
# For multi-process deployments, move this to Redis.
# ---------------------------------------------------------------------------
_rate_lock = threading.Lock()
_failed: dict[str, list[datetime]] = defaultdict(list)
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _check_rate_limit(email: str) -> None:
    with _rate_lock:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=LOCKOUT_MINUTES)
        recent = [t for t in _failed[email] if t > cutoff]
        _failed[email] = recent
        if len(recent) >= MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed attempts. Try again in {LOCKOUT_MINUTES} minutes.",
            )


def _record_failure(email: str) -> None:
    with _rate_lock:
        _failed[email].append(datetime.now(timezone.utc))


def _clear_failures(email: str) -> None:
    with _rate_lock:
        _failed.pop(email, None)


def _set_session_cookie(response: Response, token: str) -> None:
    # No max_age → session cookie → browser deletes it when the tab/window closes
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=SECURE_COOKIE,
        samesite="lax",
        path="/",
    )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(request: LoginRequest, response: Response, db: Session = Depends(get_db)):
    _check_rate_limit(request.email)

    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.password_hash):
        _record_failure(request.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled.")

    _clear_failures(request.email)
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(user.id)
    _set_session_cookie(response, token)

    return {
        "success": True,
        "user_id": str(user.id),
        "email": user.email,
        "role": user.role,
        "must_change_password": user.must_change_password,
    }


# ---------------------------------------------------------------------------
# Logout — invalidates the token server-side and clears the cookie
# ---------------------------------------------------------------------------

@router.post("/logout")
def logout(
    response: Response,
    session: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if session:
        jti = get_jti(session)
        if jti and not db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
            db.add(RevokedToken(jti=jti))
            db.commit()

    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"success": True}


# ---------------------------------------------------------------------------
# /me — lets the frontend verify an existing session on page load
# ---------------------------------------------------------------------------

@router.get("/me")
def get_me(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "user_id": str(user.id),
        "email": user.email,
        "role": user.role,
        "must_change_password": user.must_change_password,
    }


# ---------------------------------------------------------------------------
# Create user (admin only)
# ---------------------------------------------------------------------------

class CreateUserRequest(BaseModel):
    email: str
    role: str
    tenant_id: str


@router.post("/create-user")
def create_user(
    request: CreateUserRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = db.query(User).filter(User.id == user_id).first()
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    if db.query(User).filter(User.email == request.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    temp_password = secrets.token_urlsafe(12)
    new_user = User(
        id=str(uuid.uuid4()),
        tenant_id=request.tenant_id,
        email=request.email,
        password_hash=hash_password(temp_password),
        role=request.role,
        is_active=True,
        must_change_password=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    send_temp_password_email(request.email, temp_password)
    return {"success": True, "user_id": new_user.id, "email": new_user.email}


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    response: Response,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(request.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Old password is incorrect")

    if len(request.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")

    user.password_hash = hash_password(request.new_password)
    user.must_change_password = False
    db.commit()

    # Issue a fresh token so the updated must_change_password=False is in the new cookie
    _set_session_cookie(response, create_access_token(user.id))

    return {"success": True, "message": "Password changed successfully"}


# ---------------------------------------------------------------------------
# User stats (admin only)
# ---------------------------------------------------------------------------

@router.get("/user-stats")
def get_user_stats(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    return {
        "total_users": db.query(User).filter(User.tenant_id == user.tenant_id, User.is_active == True).count(),
        "active_admins": db.query(User).filter(User.tenant_id == user.tenant_id, User.role == "admin", User.is_active == True).count(),
        "active_users": db.query(User).filter(User.tenant_id == user.tenant_id, User.role == "user", User.is_active == True).count(),
    }
