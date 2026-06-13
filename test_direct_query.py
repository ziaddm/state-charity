"""
Direct database query to see what's actually in patient_visits
"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

print("=" * 80)
print("CHECKING PATIENT_VISITS TABLE")
print("=" * 80)

with engine.connect() as conn:
    # Get all records
    result = conn.execute(text("""
        SELECT
            patient_id,
            record_id,
            tenant_id,
            visit_date,
            source_file_hash,
            created_at
        FROM patient_visits
        ORDER BY created_at DESC
    """))

    records = list(result)

    print(f"\nTotal records: {len(records)}\n")

    if len(records) == 0:
        print("✓ Table is EMPTY - ready for fresh upload!")
    else:
        print("Records in table:")
        print("-" * 80)
        for idx, row in enumerate(records, 1):
            print(f"{idx}. Patient: {row.patient_id} | Record: {row.record_id}")
            print(f"   Tenant: {row.tenant_id}")
            print(f"   Visit: {row.visit_date}")
            print(f"   Hash: {row.source_file_hash[:16] if row.source_file_hash else 'None'}...")
            print(f"   Created: {row.created_at}")
            print("-" * 80)

print("\n" + "=" * 80)
