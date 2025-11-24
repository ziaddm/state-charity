from sqlalchemy import Column, String, Integer, Date, DateTime, Numeric, ForeignKey, Index
from datetime import datetime, timezone
from .base import Base

class PatientVisit(Base):
    """Store validated patient visit records for analytics"""
    __tablename__ = "patient_visits"

    # Primary key
    id = Column(String, primary_key=True)

    # Foreign keys
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False, index=True)

    # Patient Demographics
    patient_id = Column(String, nullable=False, index=True)  # MRN or patient identifier
    last_name = Column(String)
    first_name = Column(String)
    middle_initial = Column(String(1))
    date_of_birth = Column(Date, index=True)
    gender = Column(String(1), index=True)  # M, F, U
    ethnicity = Column(String, index=True)
    race = Column(String, index=True)

    # Address
    street_address = Column(String)
    city = Column(String)
    state = Column(String(2))
    zip = Column(String(10))
    census_tract = Column(String)

    # Visit Information
    record_id = Column(String, nullable=False, index=True)  # Unique encounter/visit ID
    visit_date = Column(Date, nullable=False, index=True)
    visit_time = Column(String)
    invoice_number = Column(String)
    new_patient = Column(String(1))  # Y/N
    visit_type = Column(String, index=True)  # initial, follow-up

    # Clinical
    icd_1 = Column(String)
    icd_2 = Column(String)
    icd_3 = Column(String)
    icd_4 = Column(String)
    icd_5 = Column(String)

    # Financial
    family_size = Column(Integer)
    family_income = Column(Numeric(12, 2))
    total_charges = Column(Numeric(12, 2), index=True)
    total_payment_received = Column(Numeric(12, 2))

    # Insurance/Payer
    payor_source = Column(String, index=True)  # MC, MD, PR, UN, OT
    insurance_name = Column(String)

    # Flags and Categories
    claim_type = Column(String(1), index=True)  # I, O, E (Inpatient, Outpatient, Emergency)
    uncompensated_visit = Column(String(1), index=True)  # Y/N - charity care flag
    location_code = Column(String)
    record_type = Column(String)

    # Family Care History
    medicaid_family_care_ever = Column(String(1))  # Y/N
    uninsured_family_care_ever = Column(String(1))  # Y/N
    migrant_farmer = Column(String(1))  # Y/N

    # Metadata
    source_file_hash = Column(String, nullable=False, index=True)  # To prevent duplicates
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Composite index for deduplication
    __table_args__ = (
        Index('idx_patient_record_unique', 'tenant_id', 'patient_id', 'record_id', unique=False),
        Index('idx_visit_date_tenant', 'visit_date', 'tenant_id'),
        Index('idx_analytics_query', 'tenant_id', 'visit_date', 'gender', 'payor_source'),
    )
