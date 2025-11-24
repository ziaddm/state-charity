"""
Create an admin user in the database
"""
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import bcrypt

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Import models directly
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from datetime import datetime, timezone

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    state_code = Column(String(2))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String)
    is_active = Column(Boolean, default=False)
    must_change_password = Column(Boolean, default=True)
    last_login = Column(DateTime)
    created_by_user_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# Create admin user
db = SessionLocal()

try:
    # First, create a default tenant if it doesn't exist
    tenant_id = str(uuid.uuid4())
    tenant = db.query(Tenant).filter(Tenant.name == "Default Organization").first()

    if not tenant:
        tenant = Tenant(
            id=tenant_id,
            name="Default Organization",
            state_code="US"
        )
        db.add(tenant)
        db.commit()
        print(f"Created tenant: Default Organization (ID: {tenant_id})")
    else:
        tenant_id = tenant.id
        print(f"Using existing tenant: {tenant.name} (ID: {tenant_id})")

    # Check if admin user already exists
    existing_admin = db.query(User).filter(User.email == "admin@charity.local").first()

    if existing_admin:
        print(f"Admin user already exists with email: admin@charity.local")
        print("Deleting existing admin...")
        db.delete(existing_admin)
        db.commit()

    # Hash the password
    password = "admin123"
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Create admin user
    admin_user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        email="admin@charity.local",
        password_hash=hashed_password,
        role="admin",
        is_active=True,
        must_change_password=False
    )

    db.add(admin_user)
    db.commit()

    print(f"\n[SUCCESS] Admin user created!")
    print(f"Email: admin@charity.local")
    print(f"Password: admin123")
    print(f"Role: admin")
    print(f"User ID: {admin_user.id}")

except Exception as e:
    db.rollback()
    print(f"[ERROR] Failed to create admin user: {e}")
    raise
finally:
    db.close()
