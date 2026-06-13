import sys
sys.path.insert(0, r"C:\Users\ziadm\Desktop\VS Code\compliance-analytics\compliance-backend")

import uuid
from datetime import date, datetime, timezone
from app.database.connection import SessionLocal
from app.database.models import PatientVisit, ValidationRun

db = SessionLocal()

# Check if test run exists, create if not
test_run = db.query(ValidationRun).filter(ValidationRun.id == "test_run_001").first()
if not test_run:
    test_run = ValidationRun(
        id="test_run_001",
        tenant_id="c86cadf8-557b-4262-a6c4-02386a7de965",
        created_by_user_id="ce40002d-e207-4b88-b898-00d2f761c574",
        source_filename="test_data.csv",
        status="completed",
        record_count=1,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc)
    )
    db.add(test_run)
    db.commit()
    print("[OK] Created test run")
else:
    print("[OK] Using existing test run")

# Create a test patient visit record
test_visit = PatientVisit(
    id=str(uuid.uuid4()),
    tenant_id="c86cadf8-557b-4262-a6c4-02386a7de965",  # Your tenant ID from the logs
    run_id="test_run_001",

    # Patient Demographics
    patient_id="TEST001",
    last_name="Smith",
    first_name="John",
    middle_initial="A",
    date_of_birth=date(1985, 6, 15),
    gender="M",
    ethnicity="Not Hispanic or Latino",
    race="White",

    # Address
    street_address="123 Main St",
    city="Newark",
    state="NJ",
    zip="07102",
    census_tract="34013001600",

    # Visit Information
    record_id="VISIT001",
    visit_date=date(2024, 11, 15),
    visit_time="09:30",
    invoice_number="INV-2024-001",
    new_patient="N",
    visit_type="Follow-up",

    # Clinical
    icd_1="Z00.00",
    icd_2="E11.9",

    # Financial
    family_size=3,
    family_income=45000.00,
    total_charges=250.00,
    total_payment_received=250.00,

    # Insurance/Payer
    payor_source="MC",
    insurance_name="Medicaid",

    # Flags
    claim_type="O",
    uncompensated_visit="N",
    medicaid_family_care_ever="Y",
    uninsured_family_care_ever="N",
    migrant_farmer="N",

    # Metadata
    source_file_hash="test_hash_" + uuid.uuid4().hex[:16],
    created_at=datetime.now()
)

db.add(test_visit)
db.commit()
db.refresh(test_visit)

print(f"[OK] Successfully inserted test record with ID: {test_visit.id}")
print(f"  Patient: {test_visit.first_name} {test_visit.last_name}")
print(f"  Visit Date: {test_visit.visit_date}")
print(f"  Total Charges: ${test_visit.total_charges}")

db.close()
