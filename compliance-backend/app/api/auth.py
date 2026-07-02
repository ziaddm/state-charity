import os
import secrets
import uuid
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import RevokedToken, Tenant, User
from app.services.audit import record_event
from app.services.authz import is_platform_admin, require_admin
from app.services.email import send_temp_password_email
from app.services.password import hash_password, verify_password
from app.services.tokens import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_user,
    get_jti,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "session"
SECURE_COOKIE = os.getenv("ENVIRONMENT", "development") == "production"

# SameSite policy for the session cookie. "lax" works when the frontend and
# API share a registrable domain (e.g. CloudFront routing /api/* to the ALB).
# If they are on different domains set COOKIE_SAMESITE=none, which forces
# Secure and relies on the Origin-check middleware in main.py for CSRF.
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").lower()
if COOKIE_SAMESITE not in ("lax", "strict", "none"):
    COOKIE_SAMESITE = "lax"
if COOKIE_SAMESITE == "none":
    SECURE_COOKIE = True

# ---------------------------------------------------------------------------
# In-memory rate limiter — tracks failed login attempts per email address.
# Resets automatically after LOCKOUT_MINUTES. Survives for the process lifetime.
# For multi-process deployments, move this to Redis.
# ---------------------------------------------------------------------------
_rate_lock = threading.Lock()
_failed: dict[str, list[datetime]] = {}
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _check_rate_limit(email: str) -> None:
    with _rate_lock:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=LOCKOUT_MINUTES)
        recent = [t for t in _failed.get(email, []) if t > cutoff]
        if recent:
            _failed[email] = recent
        else:
            _failed.pop(email, None)
        if len(recent) >= MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed attempts. Try again in {LOCKOUT_MINUTES} minutes.",
            )


def _record_failure(email: str) -> None:
    with _rate_lock:
        _failed.setdefault(email, []).append(datetime.now(timezone.utc))


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
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def _revoke_token(db: Session, token: str) -> None:
    jti = get_jti(token)
    if jti and not db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        db.add(RevokedToken(jti=jti))
        db.commit()


def _prune_revoked_tokens(db: Session) -> None:
    """Delete revocation rows old enough that the token has expired anyway."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES, days=1)
    db.query(RevokedToken).filter(RevokedToken.revoked_at < cutoff).delete()
    db.commit()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(request: LoginRequest, response: Response, db: Session = Depends(get_db)):
    email = _normalize_email(request.email)
    _check_rate_limit(email)

    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(request.password, user.password_hash):
        _record_failure(email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    # Same generic message as bad credentials so account status is not leaked
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    _clear_failures(email)
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(user.id)
    _set_session_cookie(response, token)
    record_event(db, "login", user_id=user.id, tenant_id=user.tenant_id)

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
        _revoke_token(db, session)
        _prune_revoked_tokens(db)

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
# /refresh — reissues the session cookie so active users are not logged out
# mid-work when the token hits its fixed expiry. The frontend calls this
# periodically while the user is active.
# ---------------------------------------------------------------------------

@router.post("/refresh")
def refresh_session(
    response: Response,
    user_id: str = Depends(get_current_user),
):
    _set_session_cookie(response, create_access_token(user_id))
    return {"success": True}


# ---------------------------------------------------------------------------
# Create user (admin only; tenant admins may only create users in their own
# tenant, platform admins in any tenant)
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
    current_user = require_admin(user_id, db)

    if request.role not in ("user", "admin"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be 'user' or 'admin'")

    if request.tenant_id != current_user.tenant_id and not is_platform_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create users for your own facility",
        )

    if not db.query(Tenant).filter(Tenant.id == request.tenant_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant does not exist")

    email = _normalize_email(request.email)
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    temp_password = secrets.token_urlsafe(12)
    new_user = User(
        id=str(uuid.uuid4()),
        tenant_id=request.tenant_id,
        email=email,
        password_hash=hash_password(temp_password),
        role=request.role,
        is_active=True,
        must_change_password=True,
        created_by_user_id=current_user.id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    record_event(db, "user_created", user_id=current_user.id, tenant_id=request.tenant_id)

    email_sent = send_temp_password_email(email, temp_password)
    result = {
        "success": True,
        "user_id": new_user.id,
        "email": new_user.email,
        "email_sent": email_sent,
    }
    if not email_sent:
        # Email delivery failed — return the password once, over TLS, to the
        # admin who created the account, so they can pass it on securely.
        # It is never logged or stored in plain text.
        result["temp_password"] = temp_password
        result["message"] = (
            "Email delivery failed or is not configured. Share this temporary "
            "password with the user through a secure channel; they must change "
            "it on first login."
        )
    return result


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
    session: Optional[str] = Cookie(default=None),
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

    if request.new_password == request.old_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different from the old password")

    user.password_hash = hash_password(request.new_password)
    user.must_change_password = False
    # Invalidates every token issued before this moment (see tokens.get_current_user)
    user.password_changed_at = datetime.now(timezone.utc)
    db.commit()
    record_event(db, "password_changed", user_id=user.id, tenant_id=user.tenant_id)

    # Explicitly revoke the token used for this request, then issue a fresh one
    if session:
        _revoke_token(db, session)
    _set_session_cookie(response, create_access_token(user.id))

    return {"success": True, "message": "Password changed successfully"}


# ---------------------------------------------------------------------------
# User stats (admin only; platform admins see global numbers)
# ---------------------------------------------------------------------------

@router.get("/user-stats")
def get_user_stats(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = require_admin(user_id, db)

    query = db.query(User)
    if not is_platform_admin(user):
        query = query.filter(User.tenant_id == user.tenant_id)

    return {
        "total_users": query.filter(User.is_active == True).count(),
        "active_admins": query.filter(User.role == "admin", User.is_active == True).count(),
        "active_users": query.filter(User.role == "user", User.is_active == True).count(),
    }
