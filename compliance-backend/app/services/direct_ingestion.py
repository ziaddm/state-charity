"""
Direct CSV Ingestion Service
=============================

This service provides direct CSV ingestion into the patient_visits table,
using the validation pipeline to transform to canonical schema.
"""
import hashlib
import uuid
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database.models import PatientVisit
from app.adapters.report_adapter import ReportAdapter

logger = logging.getLogger(__name__)


def ingest_csv_directly(
    db: Session,
    csv_path: Path,
    tenant_id: str,
) -> int:
    """
    Ingest CSV file into patient_visits table using the validation pipeline
    to transform it to canonical schema first.

    Args:
        db: Database session
        csv_path: Path to CSV file
        tenant_id: Tenant identifier (e.g., "acme_health")

    Returns:
        Number of records ingested
    """
    logger.info(f"Starting direct ingestion for tenant {tenant_id} from {csv_path}")

    # Calculate file hash for deduplication
    with open(csv_path, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    # Check if this file has already been ingested
    existing = db.query(PatientVisit).filter(
        and_(
            PatientVisit.tenant_id == tenant_id,
            PatientVisit.source_file_hash == file_hash
        )
    ).first()

    if existing:
        logger.info(f"File with hash {file_hash} already ingested, skipping")
        return 0

    # Use ReportAdapter to transform CSV to canonical schema
    try:
        adapter = ReportAdapter(config_dir="config", output_dir="output")

        artifact = adapter.generate(
            tenant_id=tenant_id,
            state_code="NJ",  # Default to NJ
            source_file=str(csv_path),
            run_id=f"analytics_{uuid.uuid4().hex[:8]}"
        )

        if not artifact.canonical_data:
            logger.error("No canonical data generated from CSV")
            return 0

        logger.info(f"Generated {len(artifact.canonical_data)} canonical records")

    except Exception as e:
        logger.error(f"Failed to generate canonical data: {e}", exc_info=True)
        return 0

    records_added = 0

    # Helper functions for safe type conversion
    def safe_date(val):
        if not val or val is None:
            return None
        if isinstance(val, datetime):
            return val.date()
        return val

    def safe_str(val):
        if val is None or val == '':
            return None
        return str(val).strip()

    def safe_float(val):
        if val is None or val == '':
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def safe_int(val):
        if val is None or val == '':
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    # Process each canonical record (already in state schema format)
    for record in artifact.canonical_data:
        # Extract patient and record identifiers from canonical data
        patient_id = safe_str(record.get('patient_id'))
        record_id = safe_str(record.get('record_id'))

        if not patient_id or not record_id:
            logger.warning(f"Skipping record with missing patient_id or record_id")
            continue

        # Check for duplicate record
        existing_record = db.query(PatientVisit).filter(
            and_(
                PatientVisit.tenant_id == tenant_id,
                PatientVisit.patient_id == patient_id,
                PatientVisit.record_id == record_id
            )
        ).first()

        if existing_record:
            continue

        # Create PatientVisit record from canonical data
        visit = PatientVisit(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            patient_id=patient_id,
            record_id=record_id,
            source_file_hash=file_hash,
            run_id=artifact.run_id,

            # Dates
            visit_date=safe_date(record.get('visit_date')),
            date_of_birth=safe_date(record.get('date_of_birth')),
            visit_time=safe_str(record.get('visit_time')),

            # Demographics
            last_name=safe_str(record.get('last_name')),
            first_name=safe_str(record.get('first_name')),
            middle_initial=safe_str(record.get('middle_initial')),
            gender=safe_str(record.get('gender')),
            ethnicity=safe_str(record.get('ethnicity')),
            race=safe_str(record.get('race')),

            # Address
            street_address=safe_str(record.get('street_address')),
            city=safe_str(record.get('city')),
            state=safe_str(record.get('state')),
            zip=safe_str(record.get('zip')),
            census_tract=safe_str(record.get('census_tract')),

            # Visit Information
            invoice_number=safe_str(record.get('invoice_number')),
            visit_type=safe_str(record.get('visit_type')),
            new_patient=safe_str(record.get('new_patient')),
            claim_type=safe_str(record.get('claim_type')),
            location_code=safe_str(record.get('location_code')),
            record_type=safe_str(record.get('record_type')),

            # Financial
            total_charges=safe_float(record.get('total_charges')),
            total_payment_received=safe_float(record.get('total_payment_received')),
            family_income=safe_float(record.get('family_income')),
            family_size=safe_int(record.get('family_size')),

            # Insurance/Payer
            payor_source=safe_str(record.get('payor_source')),
            insurance_name=safe_str(record.get('insurance_name')),

            # Clinical (ICD codes)
            icd_1=safe_str(record.get('icd_1')),
            icd_2=safe_str(record.get('icd_2')),
            icd_3=safe_str(record.get('icd_3')),
            icd_4=safe_str(record.get('icd_4')),
            icd_5=safe_str(record.get('icd_5')),

            # Flags
            uncompensated_visit=safe_str(record.get('uncompensated_visit')),
            medicaid_family_care_ever=safe_str(record.get('medicaid_family_care_ever')),
            uninsured_family_care_ever=safe_str(record.get('uninsured_family_care_ever')),
            migrant_farmer=safe_str(record.get('migrant_farmer')),
        )

        db.add(visit)
        records_added += 1

        # Batch commit every 100 records
        if records_added % 100 == 0:
            db.commit()
            logger.info(f"Committed {records_added} records")

    # Final commit
    db.commit()

    logger.info(f"Direct ingestion complete: {records_added} records added")
    return records_added
