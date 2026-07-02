"""
Authorization helpers.

Two admin tiers exist:

- Tenant admin (role == "admin"): manages users inside their own tenant and
  sees only their own tenant's data.
- Platform admin: a tenant admin whose email is listed in the
  PLATFORM_ADMIN_EMAILS environment variable (comma-separated). Only platform
  admins may create/delete tenants or view users across tenants.

If PLATFORM_ADMIN_EMAILS is unset, no one has platform powers (fail closed);
tenant management must then be done via backend scripts.
"""
import os

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database.models import User

PLATFORM_ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.getenv("PLATFORM_ADMIN_EMAILS", "").split(",")
    if e.strip()
}


def is_platform_admin(user: User) -> bool:
    return user.role == "admin" and (user.email or "").lower() in PLATFORM_ADMIN_EMAILS


def require_admin(user_id: str, db: Session) -> User:
    """Return the user if they are an admin (any tier), else 403."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_platform_admin(user_id: str, db: Session) -> User:
    """Return the user if they are a platform admin, else 403."""
    user = require_admin(user_id, db)
    if not is_platform_admin(user):
        raise HTTPException(
            status_code=403,
            detail=(
                "Platform admin access required. Add this admin's email to the "
                "PLATFORM_ADMIN_EMAILS environment variable to grant tenant management."
            ),
        )
    return user
