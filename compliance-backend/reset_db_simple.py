"""
Simplified database reset script
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect, MetaData

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
print(f"Looking for .env at: {env_path}")
print(f".env exists: {env_path.exists()}")
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file")

print(f"DATABASE_URL value: {DATABASE_URL[:30]}... (truncated)")
print(f"DATABASE_URL length: {len(DATABASE_URL)}")

print(f"Connecting to database...")
if '@' in DATABASE_URL:
    print(f"URL (password hidden): ...@{DATABASE_URL.split('@')[1]}")
else:
    print(f"URL loaded: {len(DATABASE_URL)} characters")

engine = create_engine(DATABASE_URL)

# Get all table names
inspector = inspect(engine)
existing_tables = inspector.get_table_names()

print(f"\nFound {len(existing_tables)} existing tables:")
for table in existing_tables:
    print(f"  - {table}")

# Ask for confirmation
print("\n[WARNING] This will DROP all existing tables and data!")
confirm = input("Type 'yes' to proceed: ")

if confirm.lower() != 'yes':
    print("Aborted.")
    exit(0)

print("\nDropping all tables...")
with engine.connect() as conn:
    # Drop all tables (including alembic_version if it exists)
    for table in existing_tables:
        print(f"  Dropping {table}...")
        conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
    conn.commit()

print("\nRecreating tables from SQLAlchemy models...")

# Import models AFTER we've already created the engine
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, ForeignKey
from datetime import datetime, timezone

Base = declarative_base()

# Define models directly here
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

class ValidationRun(Base):
    __tablename__ = "runs"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    created_by_user_id = Column(String, ForeignKey("users.id"))
    state_code = Column(String(2))
    status = Column(String)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    record_count = Column(Integer, default=0)
    valid_count = Column(Integer, default=0)
    source_filename = Column(String)
    source_file_hash = Column(String)
    submission_file_path = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ValidationError(Base):
    __tablename__ = "errors"
    id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    row_number = Column(Integer)
    field_name = Column(String)
    error_type = Column(String)
    error_message = Column(Text)
    severity = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"))
    action = Column(String, nullable=False)
    resource_type = Column(String)
    resource_id = Column(String)
    details = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# Create all tables
Base.metadata.create_all(bind=engine)

# Verify new tables
inspector = inspect(engine)
new_tables = inspector.get_table_names()

print(f"\n[SUCCESS] Database reset complete!")
print(f"Created {len(new_tables)} tables:")
for table in new_tables:
    print(f"  - {table}")

print("\nYou now have a clean database ready for analytics implementation.")
