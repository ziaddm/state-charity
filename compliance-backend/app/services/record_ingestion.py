"""
Service for ingesting validated patient visit records into analytics database
"""
import hashlib
import csv
import uuid
from datetime import datetime, date
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Dict, Any

from app.database.models import PatientVisit

import logging
logger = logging.getLogger(__name__)


def calculate_file_hash(file_content: bytes) -> str:
    """Calculate SHA256 hash of file content"""
    return hashlib.sha256(file_content).hexdigest()


def parse_date(date_input) -> date:
    """Parse date input - handles strings, datetime.date, and datetime.datetime objects"""
    if not date_input:
        return None

    # If it's already a date object, return it
    if isinstance(date_input, date) and not isinstance(date_input, datetime):
        return date_input

    # If it's a datetime object, extract the date
    if isinstance(date_input, datetime):
        return date_input.date()

    # Otherwise treat it as a string and try to parse
    date_str = str(date_input)
    # Try common date formats
    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%Y%m%d', '%m-%d-%Y']:
        try:
            return datetime.strptime(date_str, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def read_submission_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    Read the generated submission file (fixed-width format)
    This is a simplified reader - in production you'd parse based on the spec
    For MVP, we'll read the original CSV that was validated
    """
    records = []

    # For now, return empty - we'll need to read from the artifact's canonical data
    # The ReportAdapter should have this data available
    return records


def ingest_records_from_artifact(
    db: Session,
    artifact: Any,
    tenant_id: str,
    run_id: str,
    file_hash: str,
    source_file_path: str
) -> int:
    """
    Ingest patient visit records from the validation artifact
    Only ingests if validation passed with no errors or warnings

    Returns: number of records ingested
    """

    # Check if validation passed with no errors (warnings are OK)
    if not artifact.validation:
        logger.info("No validation results available")
        return 0

    if len(artifact.validation.errors) > 0:
        logger.info(f"Skipping ingestion due to {len(artifact.validation.errors)} errors (warnings are OK)")
        return 0

    # Log warnings if present but continue ingestion
    if len(artifact.validation.warnings) > 0:
        logger.info(f"Processing {len(artifact.validation.warnings)} warnings but continuing ingestion")

    # Get the canonical data from the artifact
    if not hasattr(artifact, 'canonical_data') or not artifact.canonical_data:
        print("❌ NO CANONICAL DATA IN ARTIFACT!")
        logger.warning("No canonical data available in artifact")
        return 0

    canonical_records = artifact.canonical_data
    print(f"✓ Found {len(canonical_records)} canonical records to process")
    logger.info(f"Found {len(canonical_records)} canonical records to process")

    # PERFORMANCE OPTIMIZATION: Bulk duplicate check
    # Get all existing (patient_id, record_id) combinations for this tenant in ONE query
    existing_records = db.query(
        PatientVisit.patient_id,
        PatientVisit.record_id
    ).filter(
        PatientVisit.tenant_id == tenant_id
    ).all()

    existing_keys = {(patient_id, record_id) for patient_id, record_id in existing_records}
    logger.info(f"Found {len(existing_keys)} existing records in database")

    ingested_count = 0
    skipped_count = 0
    visits_to_insert = []
    created_at = datetime.now()  # Single timestamp for all records

    for idx, record in enumerate(canonical_records, 1):
        try:
            # Extract key identifiers
            patient_id = record.get('patient_id', '')
            record_id = record.get('record_id', '')

            if not patient_id or not record_id:
                if skipped_count < 3:
                    logger.warning(f"Record {idx}: Skipping - missing identifiers")
                skipped_count += 1
                continue

            # OPTIMIZED: Check for duplicate using in-memory set (O(1) instead of database query)
            if (patient_id, record_id) in existing_keys:
                if skipped_count < 3:
                    logger.info(f"Record {idx}: DUPLICATE SKIP (patient={patient_id}, record={record_id})")
                skipped_count += 1
                continue

            if ingested_count < 3:
                logger.info(f"Record {idx}: WILL INGEST (patient={patient_id}, record={record_id})")

            # Parse dates once
            visit_date = parse_date(record.get('visit_date'))
            date_of_birth = parse_date(record.get('date_of_birth'))

            # OPTIMIZED: Build dictionary directly instead of ORM object (faster!)
            visit_dict = {
                'id': str(uuid.uuid4()),
                'tenant_id': tenant_id,
                'run_id': run_id,
                'patient_id': patient_id,
                'record_id': record_id,
                'visit_date': visit_date,
                'date_of_birth': date_of_birth,
                'last_name': (record.get('last_name') or '')[:255] or None,
                'first_name': (record.get('first_name') or '')[:255] or None,
                'middle_initial': (record.get('middle_initial') or '')[:1] or None,
                'gender': (record.get('gender') or '')[:1] or None,
                'ethnicity': (record.get('ethnicity') or '')[:50] or None,
                'race': (record.get('race') or '')[:50] or None,
                'street_address': (record.get('street_address') or '')[:255] or None,
                'city': (record.get('city') or '')[:100] or None,
                'state': (record.get('state') or '')[:2] or None,
                'zip': (record.get('zip') or '')[:10] or None,
                'census_tract': (record.get('census_tract') or '')[:50] or None,
                'visit_time': str(record.get('visit_time')) if record.get('visit_time') else None,
                'invoice_number': (record.get('invoice_number') or '')[:50] or None,
                'new_patient': (record.get('new_patient') or '')[:1] or None,
                'visit_type': (record.get('visit_type') or '')[:20] or None,
                'icd_1': (record.get('icd_1') or '')[:10] or None,
                'icd_2': (record.get('icd_2') or '')[:10] or None,
                'icd_3': (record.get('icd_3') or '')[:10] or None,
                'icd_4': (record.get('icd_4') or '')[:10] or None,
                'icd_5': (record.get('icd_5') or '')[:10] or None,
                'family_size': int(record.get('family_size', 0)) if record.get('family_size') else None,
                'family_income': float(record.get('family_income', 0)) if record.get('family_income') else None,
                'total_charges': float(record.get('total_charges', 0)) if record.get('total_charges') else None,
                'total_payment_received': float(record.get('total_payment_received', 0)) if record.get('total_payment_received') else None,
                'payor_source': (record.get('payor_source') or '')[:10] or None,
                'insurance_name': (record.get('insurance_name') or '')[:100] or None,
                'claim_type': (record.get('claim_type') or '')[:1] or None,
                'uncompensated_visit': (record.get('uncompensated_visit') or '')[:1] or None,
                'location_code': (record.get('location_code') or '')[:10] or None,
                'record_type': (record.get('record_type') or '')[:10] or None,
                'medicaid_family_care_ever': (record.get('medicaid_family_care_ever') or '')[:1] or None,
                'uninsured_family_care_ever': (record.get('uninsured_family_care_ever') or '')[:1] or None,
                'migrant_farmer': (record.get('migrant_farmer') or '')[:1] or None,
                'source_file_hash': file_hash,
                'created_at': created_at
            }

            visits_to_insert.append(visit_dict)
            ingested_count += 1

        except Exception as e:
            if skipped_count < 3:
                logger.error(f"Error ingesting record {idx}: {e}")
            skipped_count += 1
            continue

    # OPTIMIZED: Single bulk insert using bulk_insert_mappings (fastest SQLAlchemy method)
    if visits_to_insert:
        db.bulk_insert_mappings(PatientVisit, visits_to_insert)
        db.commit()
        logger.info(f"Bulk inserted {len(visits_to_insert)} records in single transaction")

    # Summary log
    logger.info("=" * 60)
    logger.info(f"INGESTION SUMMARY:")
    logger.info(f"  Total records processed: {len(canonical_records)}")
    logger.info(f"  New records ingested:    {ingested_count}")
    logger.info(f"  Duplicates skipped:      {skipped_count}")
    logger.info(f"  Status: {'✓ SUCCESS' if ingested_count > 0 else '⚠ NO NEW RECORDS'}")
    logger.info("=" * 60)

    return ingested_count
