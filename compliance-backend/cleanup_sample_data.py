"""
Clean up all the sample validation runs and user data, keep only Acme Health tenant
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    # Get Acme Health tenant ID
    result = db.execute(text("SELECT id FROM tenants WHERE name = 'Acme Health'")).fetchone()

    if result:
        acme_tenant_id = result[0]
        print(f"Found Acme Health tenant: {acme_tenant_id}")

        # Delete errors first (foreign key to runs)
        errors_deleted = db.execute(text("""
            DELETE FROM errors
            WHERE run_id IN (
                SELECT id FROM runs WHERE tenant_id = :tenant_id
            )
        """), {"tenant_id": acme_tenant_id})
        print(f"Deleted {errors_deleted.rowcount} error records")

        # Delete validation runs
        runs_deleted = db.execute(text("""
            DELETE FROM runs WHERE tenant_id = :tenant_id
        """), {"tenant_id": acme_tenant_id})
        print(f"Deleted {runs_deleted.rowcount} validation runs")

        # Delete the user
        user_deleted = db.execute(text("""
            DELETE FROM users WHERE tenant_id = :tenant_id
        """), {"tenant_id": acme_tenant_id})
        print(f"Deleted {user_deleted.rowcount} users")

        db.commit()
        print("\n[SUCCESS] Cleaned up all sample data!")
        print("Acme Health tenant is kept for dropdown selection")
    else:
        print("Acme Health tenant not found")

except Exception as e:
    db.rollback()
    print(f"[ERROR] {e}")
finally:
    db.close()
