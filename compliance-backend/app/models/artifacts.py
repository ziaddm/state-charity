"""
Data Models - Artifacts
========================

WHAT THIS FILE DOES:
This file defines the data structures (containers) that hold results from the compliance pipeline.
Think of these as "boxes" that organize all the information we collect during report generation.

FOR NON-TECHNICAL READERS:
When we process a hospital's data file, we create several outputs:
1. A submission file (the actual file sent to the state)
2. A validation report (list of errors and warnings found)
3. Control totals (summary numbers to verify everything adds up correctly)
4. A manifest (summary of what happened)

This file defines what information goes in each of those outputs.

THREE MAIN DATA STRUCTURES:
1. ValidationResult - stores all errors and warnings found during quality checks
2. ControlTotals - stores summary numbers (row counts, dollar totals, breakdowns by type)
3. ReportArtifact - the complete package of everything generated (files + results + metadata)

REAL-WORLD ANALOGY:
Like a filing folder from processing a mortgage application:
- Application form (submission file)
- Credit check results (validation report)
- Income verification (control totals)
- Processing summary sheet (manifest)
"""

# app/models/artifacts.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import json
import hashlib

@dataclass
class ValidationResult:
    """
    WHAT THIS IS: The report card from checking data quality

    PLAIN ENGLISH:
    After we check the hospital's data, we create this report that lists:
    - ERRORS (red flags) - serious problems that MUST be fixed before submission
    - WARNINGS (yellow flags) - things that look odd but might be okay

    ERRORS block submission (like missing patient IDs or negative charges)
    WARNINGS just flag for review (like an unusual ZIP code or name format)

    Each error/warning includes:
    - A code (like "E001" or "W004") so you know what type of problem it is
    - The row number where the problem was found
    - Which field has the issue (like "patient_id" or "visit_date")
    - A clear message explaining what's wrong
    - The actual bad value (so you can see exactly what needs fixing)

    EXAMPLE:
    Error: "Row 42, field 'patient_id' - Required field is missing (code E001)"
    Warning: "Row 100, field 'zip' - Value '12345678' longer than expected 5 digits (code W001)"
    """
    passed: bool  # True if no errors found (warnings don't block submission)
    errors: List[Dict[str, Any]] = field(default_factory=list)  # List of error messages
    warnings: List[Dict[str, Any]] = field(default_factory=list)  # List of warning messages
    row_count: int = 0  # How many rows were checked
    error_count: int = 0  # Total number of errors found
    warning_count: int = 0  # Total number of warnings found
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())  # When this check happened

@dataclass
class ControlTotals:
    """
    WHAT THIS IS: Summary numbers to verify everything adds up correctly

    PLAIN ENGLISH:
    Like balancing a checkbook - we add up all the key numbers to make sure:
    1. We didn't lose or duplicate any patient visits
    2. The dollar amounts make sense
    3. We can categorize visits by insurance type and claim type

    WHY THIS MATTERS:
    If we say we processed 1,000 visits but only 995 made it to the output file,
    that's a problem! Control totals catch these mistakes.

    WHAT WE TRACK:
    - Total rows (did we process all visits?)
    - Total charges (how much was billed across all visits?)
    - Total payments (how much was collected?)
    - Breakdown by insurance type (Medicaid, Medicare, Uninsured, etc.)
    - Breakdown by claim type (inpatient, outpatient, etc.)

    EXAMPLE:
    Row count: 1,000 visits
    Total charges: $2,500,000
    Total payments: $1,800,000
    By insurance: {Medicaid: 600, Medicare: 250, Uninsured: 150}
    """
    row_count: int  # Total number of patient visits processed
    sum_total_charges: float  # Sum of all charges across all visits (dollars)
    sum_total_payment_received: float  # Sum of all payments received (dollars)
    by_payor_source: Dict[str, int] = field(default_factory=dict)  # Count by insurance type
    by_claim_type: Dict[str, int] = field(default_factory=dict)  # Count by claim type

@dataclass
class ReportArtifact:
    """
    WHAT THIS IS: The complete package of everything we generate

    PLAIN ENGLISH:
    This is the master container that holds EVERYTHING from processing a report:
    - The submission file itself (ready to send to the state)
    - The validation results (errors and warnings found)
    - The control totals (summary numbers)
    - The manifest (summary sheet explaining what happened)
    - Tracking information (who, when, how long it took)

    THINK OF IT AS:
    A FedEx package containing:
    - The main document (submission file)
    - A packing slip (manifest)
    - Quality inspection report (validation)
    - Invoice/receipt (control totals)
    - Tracking number and timestamps (run_id, created_at)

    STATUS CAN BE:
    - "draft" - just started
    - "validating" - checking data quality
    - "errors" - found problems that block submission
    - "ready" - passed all checks, ready to submit
    - "submitted" - sent to the state
    """
    run_id: str  # Unique ID for this processing run (like a tracking number)
    tenant_id: str  # Which hospital/clinic this is for
    state_code: str  # Which state (NJ, NY, PA, etc.)
    status: str  # Current status: draft, validating, errors, ready, or submitted

    # The actual output files we create
    submission_file_path: Optional[Path] = None  # Where the state submission file was saved
    submission_file_checksum: Optional[str] = None  # SHA256 hash to verify file wasn't corrupted

    # All the results and reports
    manifest: Dict[str, Any] = field(default_factory=dict)  # Summary info about this run
    validation: Optional[ValidationResult] = None  # The data quality report (errors/warnings)
    control_totals: Optional[ControlTotals] = None  # The summary numbers

    # Tracking info for audit trail
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())  # When we started
    generation_time_seconds: Optional[float] = None  # How long it took to process
    
    def to_bundle(self, output_dir: Path) -> Dict[str, Path]:
        """
        WHAT THIS DOES: Saves all the reports and files to disk

        PLAIN ENGLISH:
        After we finish processing, this function writes everything to files:
        1. The submission file (already saved, we just reference it)
        2. manifest.json - summary of what happened
        3. validation.json - list of all errors and warnings
        4. control_totals.json - the summary numbers

        These files get saved with the run_id in the name so we can find them later.

        EXAMPLE OUTPUT FILES:
        - acme_health_NJ_20250113_abc123.txt (submission file)
        - abc123_manifest.json
        - abc123_validation.json
        - abc123_control_totals.json
        """
        # Make sure the output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        bundle = {}  # Will store the paths to all files we create

        # 1. Add the submission file (already written by the pipeline)
        if self.submission_file_path:
            bundle["submission_file"] = self.submission_file_path

        # 2. Write the manifest file (summary info)
        manifest_path = output_dir / f"{self.run_id}_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(self.manifest, f, indent=2)  # indent=2 makes it human-readable
        bundle["manifest"] = manifest_path

        # 3. Write the validation results file (errors and warnings)
        if self.validation:
            val_path = output_dir / f"{self.run_id}_validation.json"
            with open(val_path, 'w') as f:
                json.dump({
                    "passed": self.validation.passed,
                    "error_count": self.validation.error_count,
                    "warning_count": self.validation.warning_count,
                    "errors": self.validation.errors,
                    "warnings": self.validation.warnings,
                    "row_count": self.validation.row_count,
                    "timestamp": self.validation.timestamp,
                }, f, indent=2)
            bundle["validation"] = val_path

        # 4. Write the control totals file (summary numbers)
        if self.control_totals:
            ct_path = output_dir / f"{self.run_id}_control_totals.json"
            with open(ct_path, 'w') as f:
                json.dump({
                    "row_count": self.control_totals.row_count,
                    "sum_total_charges": self.control_totals.sum_total_charges,
                    "sum_total_payment_received": self.control_totals.sum_total_payment_received,
                    "by_payor_source": self.control_totals.by_payor_source,
                    "by_claim_type": self.control_totals.by_claim_type,
                }, f, indent=2)
            bundle["control_totals"] = ct_path

        return bundle  # Return the dict of all file paths we created


def compute_checksum(file_path: Path) -> str:
    """
    WHAT THIS DOES: Creates a "fingerprint" of a file

    PLAIN ENGLISH:
    This creates a unique code (called a SHA256 hash) for a file.
    If even one character in the file changes, the code will be completely different.

    WHY THIS MATTERS:
    We use this to verify files weren't corrupted or tampered with:
    - When we create a submission file, we compute its checksum
    - Later, we can recompute it to verify the file is exactly the same
    - If the checksum doesn't match, something changed the file

    EXAMPLE:
    Original file: "Hello World" → checksum: "a591a6d40bf..."
    Modified file: "Hello World!" → checksum: "c0535e4be2b..." (completely different!)
    """
    sha256 = hashlib.sha256()  # Create a SHA256 hash object
    with open(file_path, 'rb') as f:
        # Read file in chunks (8KB at a time) to handle large files efficiently
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)  # Add this chunk to the hash
    return sha256.hexdigest()  # Return the final hash as a hexadecimal string