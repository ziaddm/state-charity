# app/validation/pre_validator.py
"""
Pre-validation: Validates raw data structure before mapping.

Checks:
- Required source columns exist
- Optional source columns (generates warnings if missing)
- File format and basic structure
"""

import pandas as pd
from typing import Dict, List, Any, Tuple
from app.models.artifacts import ValidationResult
from app.schema.nj_schema import CANONICAL_VISITS_SCHEMA


def validate_raw_structure(
    df_raw: pd.DataFrame,
    tenant_mapper,
    state_code: str
) -> ValidationResult:
    """
    Validate that raw input file has required structure before mapping.

    Args:
        df_raw: Raw DataFrame from source file
        tenant_mapper: TenantMapper instance with field mappings
        state_code: Target state code

    Returns:
        ValidationResult with structural errors/warnings
    """
    errors = []
    warnings = []
    info = []

    # Get all tenant columns that we expect to map
    field_map = tenant_mapper.field_map
    constants = tenant_mapper.constants

    # Check each expected source column
    for tenant_col, canonical_field in field_map.items():
        if tenant_col not in df_raw.columns:
            # Check if there's a constant defined for this field
            if canonical_field in constants:
                # Has constant fallback - just info
                continue

            # Check if this canonical field is required
            field_spec = CANONICAL_VISITS_SCHEMA.get(canonical_field, {})
            is_required = field_spec.get("required", False)

            if is_required:
                # Missing source column for REQUIRED canonical field = ERROR
                errors.append({
                    "code": "E500",
                    "severity": "error",
                    "type": "missing_required_source_column",
                    "field": canonical_field,
                    "row": "All",
                    "message": f"CRITICAL: Missing required column '{tenant_col}' - This column is required to populate '{canonical_field}' which is mandatory for submission",
                    "action": f"Add '{tenant_col}' column to your input file"
                })
            else:
                # Missing source column for optional canonical field = WARNING
                warnings.append({
                    "code": "W603",
                    "severity": "warning",
                    "type": "missing_source_column",
                    "field": canonical_field,
                    "row": "All",
                    "message": f"Missing column '{tenant_col}' - Add this column to your CSV file to provide data for {canonical_field}",
                    "action": f"Add '{tenant_col}' column to input file"
                })

    # Note unmapped columns (extra columns in source). These are informational
    # only — an extra column is ignored by the mapper and is not a data problem,
    # so it must never block a submission.
    mapped_cols = set(field_map.keys())
    actual_cols = set(df_raw.columns) - {"__rownum"}
    unmapped_cols = actual_cols - mapped_cols

    for col in unmapped_cols:
        info.append({
            "code": "I003",
            "severity": "info",
            "type": "unmapped_tenant_column",
            "field": col,
            "row": "All",
            "message": f"Extra column '{col}' in your file - This column will be ignored (not needed for submission)",
            "action": "No action needed - column will be skipped"
        })

    # Check for empty file
    if len(df_raw) == 0:
        errors.append({
            "code": "E500",
            "severity": "error",
            "type": "empty_file",
            "field": "",
            "row": "All",
            "message": "File is empty - No data rows found",
            "action": "Add data rows to the file"
        })

    # Generate result
    passed = len(errors) == 0
    return ValidationResult(
        passed=passed,
        errors=errors,
        warnings=warnings,
        info=info,
        row_count=len(df_raw),
        error_count=len(errors),
        warning_count=len(warnings),
        info_count=len(info)
    )
