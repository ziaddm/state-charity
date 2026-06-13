"""
Check what tenants exist in the database
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, DateTime, Boolean
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

def main():
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()
        print(f"\n{'='*60}")
        print(f"Found {len(tenants)} tenant(s) in database:")
        print(f"{'='*60}\n")

        for tenant in tenants:
            print(f"ID:          {tenant.id}")
            print(f"Name:        {tenant.name}")
            print(f"State Code:  {tenant.state_code}")
            print(f"Created:     {tenant.created_at}")
            print("-" * 60)

        if len(tenants) > 1:
            print("\n⚠️  WARNING: You have multiple tenants!")
            print("You should only have 'acme_health' tenant.\n")
            print("To clean up, you can delete the extra tenants from the database.")

    finally:
        db.close()

if __name__ == "__main__":
    main()
