"""
Create a Jasfel platform admin account.

Platform admins are regular admin users whose email is listed in the
PLATFORM_ADMIN_EMAILS environment variable — that combination unlocks
tenant management (create/delete clinics) and cross-facility views.

This script:
  1. Creates a "Jasfel Analytics" tenant (platform staff home; it has no
     upload config on purpose — Jasfel staff manage clinics, not submissions)
  2. Creates an admin user in it with a one-time random password
  3. Adds the email to PLATFORM_ADMIN_EMAILS in compliance-backend/.env

Usage:
    python create_platform_admin.py ops@jasfel.com

Remember: the production environment needs the same PLATFORM_ADMIN_EMAILS
value set in its task/container configuration — this script only updates
the local .env.
"""
import argparse
import os
import re
import secrets
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'compliance-backend'))

from app.database.connection import get_db
from app.database.models import Tenant, User
from app.services.password import hash_password

JASFEL_TENANT_ID = "jasfel_analytics"
ENV_PATH = Path(__file__).parent / "compliance-backend" / ".env"


def update_env_platform_admins(email: str) -> str:
    """Add the email to PLATFORM_ADMIN_EMAILS in the local .env (idempotent)."""
    line_re = re.compile(r"^PLATFORM_ADMIN_EMAILS=(.*)$", re.MULTILINE)
    content = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""

    match = line_re.search(content)
    if match:
        current = [e.strip() for e in match.group(1).split(",") if e.strip()]
        if email.lower() in (e.lower() for e in current):
            return "already listed in PLATFORM_ADMIN_EMAILS"
        current.append(email)
        content = line_re.sub(f"PLATFORM_ADMIN_EMAILS={','.join(current)}", content)
        action = "appended to PLATFORM_ADMIN_EMAILS"
    else:
        if content and not content.endswith("\n"):
            content += "\n"
        content += f"PLATFORM_ADMIN_EMAILS={email}\n"
        action = "added PLATFORM_ADMIN_EMAILS"

    ENV_PATH.write_text(content, encoding="utf-8")
    return action


def create_platform_admin(email: str, tenant_name: str) -> None:
    email = email.strip().lower()
    db = next(get_db())
    try:
        tenant = db.query(Tenant).filter(Tenant.id == JASFEL_TENANT_ID).first()
        if not tenant:
            tenant = Tenant(
                id=JASFEL_TENANT_ID,
                name=tenant_name,
                created_at=datetime.now(timezone.utc),
            )
            db.add(tenant)
            print(f"Created tenant: {tenant_name} ({JASFEL_TENANT_ID})")
        else:
            print(f"Tenant already exists: {tenant.name} ({JASFEL_TENANT_ID})")

        if db.query(User).filter(User.email == email).first():
            print(f"User {email} already exists — no account created.")
            db.rollback()
        else:
            temp_password = secrets.token_urlsafe(12)
            user = User(
                id=str(uuid.uuid4()),
                tenant_id=JASFEL_TENANT_ID,
                email=email,
                password_hash=hash_password(temp_password),
                role="admin",
                is_active=True,
                must_change_password=True,
                created_at=datetime.now(timezone.utc),
            )
            db.add(user)
            db.commit()
            print("Created platform admin account:")
            print(f"  Email:    {email}")
            print(f"  Temporary password (change on first login): {temp_password}")

        env_result = update_env_platform_admins(email)
        print(f"Local .env: {env_result}")
        print("\nReminder: set the same PLATFORM_ADMIN_EMAILS in the production environment.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a Jasfel platform admin account")
    parser.add_argument("email", help="Email address for the platform admin")
    parser.add_argument("--tenant-name", default="Jasfel Analytics", help="Display name for the platform tenant")
    args = parser.parse_args()
    create_platform_admin(args.email, args.tenant_name)
