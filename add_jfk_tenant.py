"""
Script to add JFK Hackensack Meridian Health tenant to the database.

The admin account is created with a randomly generated temporary password
(printed once by this script) and must be changed on first login.
"""
import sys
import os
import secrets
from datetime import datetime, timezone

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'compliance-backend'))

from app.database.connection import get_db
from app.database.models.tenant import Tenant
from app.database.models.user import User
from app.services.password import hash_password
from sqlalchemy.orm import Session
import uuid

def add_jfk_tenant():
    """Add JFK Hackensack Meridian Health tenant and admin user"""
    db: Session = next(get_db())

    try:
        # Check if tenant already exists
        existing_tenant = db.query(Tenant).filter(Tenant.id == "jfk_hackensack").first()
        if existing_tenant:
            print("JFK Hackensack tenant already exists")
            return

        # Create new tenant. config_id must match the YAML filename in
        # config/tenants/ — uploads are refused without it.
        tenant = Tenant(
            id="jfk_hackensack",
            name="JFK Hackensack Meridian Health",
            state_code="NJ",
            config_id="jfk_hackensack",
            created_at=datetime.now(timezone.utc)
        )
        db.add(tenant)

        # Create admin user for this tenant with a one-time random password
        temp_password = secrets.token_urlsafe(12)
        admin_user = User(
            id=str(uuid.uuid4()),
            email="admin@jfkhackensack.com",
            password_hash=hash_password(temp_password),
            tenant_id="jfk_hackensack",
            role="admin",
            is_active=True,
            must_change_password=True,
            created_at=datetime.now(timezone.utc)
        )
        db.add(admin_user)

        db.commit()

        print("Successfully added JFK Hackensack Meridian Health tenant")
        print("  Tenant ID: jfk_hackensack")
        print("  Admin Email: admin@jfkhackensack.com")
        print(f"  Temporary Password (change on first login): {temp_password}")
        print(f"  User ID: {admin_user.id}")

    except Exception as e:
        db.rollback()
        print(f"Error adding tenant: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_jfk_tenant()
