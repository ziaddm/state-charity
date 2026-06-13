"""
Clean up duplicate tenants - keep only acme_health
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timezone

# Load environment
env_path = Path(__file__).parent / "compliance-backend" / ".env"
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    state_code = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False)
    email = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)

def main():
    db = SessionLocal()
    try:
        # Get all tenants and users
        all_tenants = db.query(Tenant).all()
        all_users = db.query(User).all()

        print(f"\nFound {len(all_tenants)} tenants")
        print(f"Found {len(all_users)} users")

        # Create acme_health tenant first if it doesn't exist
        acme = db.query(Tenant).filter(Tenant.id == "acme_health").first()
        if not acme:
            acme = Tenant(
                id="acme_health",
                name="Acme Health",
                state_code="NJ"
            )
            db.add(acme)
            db.commit()
            print("\nCreated: Acme Health (ID: acme_health, State: NJ)")

        # Update all users to point to acme_health
        print("\nUpdating users to acme_health tenant...")
        for user in all_users:
            if user.tenant_id != "acme_health":
                print(f"  Updating user {user.email}: {user.tenant_id} -> acme_health")
                user.tenant_id = "acme_health"
        db.commit()

        # Now delete all other tenants
        print("\nDeleting extra tenants...")
        for tenant in all_tenants:
            if tenant.id != "acme_health":
                print(f"  Deleting: {tenant.name} (ID: {tenant.id})")
                db.delete(tenant)
        db.commit()

        print("\n✓ Cleanup complete!\n")

        # Verify
        remaining_tenants = db.query(Tenant).all()
        remaining_users = db.query(User).all()

        print(f"Tenants remaining: {len(remaining_tenants)}")
        for t in remaining_tenants:
            print(f"  - {t.name} ({t.id}, {t.state_code})")

        print(f"\nUsers: {len(remaining_users)}")
        for u in remaining_users:
            print(f"  - {u.email} (tenant: {u.tenant_id}, role: {u.role})")

    except Exception as e:
        print(f"\nError: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
