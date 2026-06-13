"""
Script to add JFK Hackensack Meridian Health tenant to the database
"""
import sys
import os
from datetime import datetime, timezone

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'compliance-backend'))

from app.database.connection import get_db
from app.database.models.tenant import Tenant
from app.database.models.user import User
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

        # Create new tenant
        tenant = Tenant(
            id="jfk_hackensack",
            name="JFK Hackensack Meridian Health",
            created_at=datetime.now(timezone.utc)
        )
        db.add(tenant)

        # Create admin user for this tenant
        admin_user = User(
            id=str(uuid.uuid4()),
            email="admin@jfkhackensack.com",
            password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyJ7IvW6b5we",  # password: admin123
            tenant_id="jfk_hackensack",
            role="admin",
            is_active=True,
            must_change_password=False,
            created_at=datetime.now(timezone.utc)
        )
        db.add(admin_user)

        db.commit()

        print("Successfully added JFK Hackensack Meridian Health tenant")
        print(f"  Tenant ID: jfk_hackensack")
        print(f"  Admin Email: admin@jfkhackensack.com")
        print(f"  Admin Password: admin123")
        print(f"  User ID: {admin_user.id}")

    except Exception as e:
        db.rollback()
        print(f"Error adding tenant: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_jfk_tenant()
