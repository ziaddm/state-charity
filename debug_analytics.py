"""
Debug script to check patient_visits data and analytics queries
"""
from sqlalchemy import create_engine, text
from datetime import date, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env file")
    exit(1)

engine = create_engine(DATABASE_URL)

print("=" * 80)
print("DEBUGGING PATIENT_VISITS AND ANALYTICS")
print("=" * 80)

with engine.connect() as conn:
    # Check total records
    result = conn.execute(text("SELECT COUNT(*) FROM patient_visits"))
    total_count = result.scalar()
    print(f"\n1. Total records in patient_visits: {total_count}")

    if total_count == 0:
        print("   ❌ NO RECORDS FOUND - This is why analytics is empty!")
        print("   → Solution: Upload a file with 0 errors (warnings are OK)")
    else:
        print(f"   ✅ Found {total_count} records")

        # Check by tenant
        result = conn.execute(text("""
            SELECT tenant_id, COUNT(*) as count
            FROM patient_visits
            GROUP BY tenant_id
        """))
        print("\n2. Records by tenant:")
        for row in result:
            print(f"   - {row.tenant_id}: {row.count} records")

        # Check date ranges
        result = conn.execute(text("""
            SELECT
                MIN(visit_date) as earliest,
                MAX(visit_date) as latest,
                COUNT(*) as count
            FROM patient_visits
            WHERE visit_date IS NOT NULL
        """))
        row = result.fetchone()
        print(f"\n3. Date range of visits:")
        print(f"   - Earliest: {row.earliest}")
        print(f"   - Latest: {row.latest}")
        print(f"   - Records with visit_date: {row.count}")

        # Check what analytics would see (last 30 days)
        today = date.today()
        start_date = today - timedelta(days=30)

        result = conn.execute(text("""
            SELECT COUNT(*)
            FROM patient_visits
            WHERE visit_date >= :start_date
            AND visit_date <= :end_date
        """), {"start_date": start_date, "end_date": today})

        count_last_30 = result.scalar()
        print(f"\n4. Records in last 30 days ({start_date} to {today}):")
        print(f"   - Count: {count_last_30}")

        if count_last_30 == 0:
            print(f"   ❌ NO RECORDS in last 30 days!")
            print(f"   → Your data is too old or in the future")
            print(f"   → Solution: Upload new data OR change time period in analytics")
        else:
            print(f"   ✅ Found {count_last_30} records - should show in analytics")

        # Check sample records
        result = conn.execute(text("""
            SELECT
                patient_id,
                record_id,
                visit_date,
                tenant_id,
                payor_source,
                total_charges
            FROM patient_visits
            LIMIT 5
        """))

        print(f"\n5. Sample records:")
        for row in result:
            print(f"   - Patient: {row.patient_id}, Visit: {row.visit_date}, Tenant: {row.tenant_id}")
            print(f"     Payor: {row.payor_source}, Charges: ${row.total_charges}")

print("\n" + "=" * 80)
print("DEBUGGING COMPLETE")
print("=" * 80)
