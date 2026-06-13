"""
Debug script to check what's actually happening during ingestion
"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

print("=" * 80)
print("DEBUGGING PATIENT_VISITS INGESTION")
print("=" * 80)

with engine.connect() as conn:
    # Check total records
    result = conn.execute(text("SELECT COUNT(*) FROM patient_visits"))
    total = result.scalar()
    print(f"\n1. TOTAL RECORDS IN patient_visits: {total}")

    if total == 0:
        print("   ❌ Table is EMPTY!")
    else:
        # Show all records with key fields
        result = conn.execute(text("""
            SELECT
                id,
                tenant_id,
                patient_id,
                record_id,
                visit_date,
                source_file_hash,
                created_at
            FROM patient_visits
            ORDER BY created_at DESC
            LIMIT 10
        """))

        print(f"\n2. ALL RECORDS (showing last 10):")
        print("-" * 80)
        for row in result:
            print(f"   ID: {row.id}")
            print(f"   Tenant: {row.tenant_id}")
            print(f"   Patient: {row.patient_id} | Record: {row.record_id}")
            print(f"   Visit Date: {row.visit_date}")
            print(f"   File Hash: {row.source_file_hash[:16] if row.source_file_hash else 'None'}...")
            print(f"   Created: {row.created_at}")
            print("-" * 80)

        # Check for duplicates
        result = conn.execute(text("""
            SELECT
                tenant_id,
                patient_id,
                record_id,
                COUNT(*) as count
            FROM patient_visits
            GROUP BY tenant_id, patient_id, record_id
            HAVING COUNT(*) > 1
        """))

        dupes = list(result)
        if dupes:
            print(f"\n3. DUPLICATE RECORDS FOUND:")
            for row in dupes:
                print(f"   {row.tenant_id} | {row.patient_id} | {row.record_id} → {row.count} copies")
        else:
            print(f"\n3. No duplicate records found ✓")

        # Check unique patient_id + record_id combinations
        result = conn.execute(text("""
            SELECT COUNT(DISTINCT patient_id || '_' || record_id) as unique_combos
            FROM patient_visits
        """))
        unique = result.scalar()
        print(f"\n4. UNIQUE patient_id + record_id combinations: {unique}")
        if unique != total:
            print(f"   ⚠️ WARNING: {total - unique} duplicate combinations!")

print("\n" + "=" * 80)
