# app/validation/control_totals_validator.py
"""
Control Totals Validator - Cross-record validation

Per MVP Spec Section 5.2:
- Cross-record rules: uniqueness, totals, duplicates, period boundaries

Validates:
- Duplicate record IDs
- Control totals reconciliation (charges, payments)
- Period boundary checks
- Data integrity across all records
"""

import pandas as pd
from typing import Dict, List, Any, Tuple
from app.models.artifacts import ValidationResult, ControlTotals


def validate_control_totals(
    df: pd.DataFrame,
    control_totals: ControlTotals,
    state_code: str
) -> ValidationResult:
    """
    Validate cross-record rules and control totals.

    Args:
        df: Coerced canonical DataFrame
        control_totals: Computed control totals
        state_code: Target state code

    Returns:
        ValidationResult with cross-record errors/warnings
    """
    errors = []
    warnings = []

    # 1. Check for duplicate record IDs
    if 'record_id' in df.columns:
        duplicates = df[df.duplicated(subset=['record_id'], keep=False)]
        if len(duplicates) > 0:
            duplicate_ids = duplicates['record_id'].unique()
            errors.append({
                "code": "E300",
                "severity": "error",
                "type": "duplicate_record_id",
                "field": "record_id",
                "row": "Multiple",
                "message": f"Duplicate record IDs found: {len(duplicate_ids)} duplicates ({', '.join(map(str, duplicate_ids[:5]))}{'...' if len(duplicate_ids) > 5 else ''})",
                "action": "Remove or correct duplicate record IDs",
                "duplicate_count": len(duplicates),
                "duplicate_ids": list(map(str, duplicate_ids))
            })

    # 2. Validate row count matches
    if control_totals.row_count != len(df):
        errors.append({
            "code": "E500",
            "severity": "error",
            "type": "row_count_mismatch",
            "field": "",
            "row": "All",
            "message": f"Control totals row count ({control_totals.row_count}) does not match actual rows ({len(df)})",
            "action": "Contact system administrator - data corruption possible"
        })

    # 3. Validate financial totals reconciliation
    if 'total_charges' in df.columns:
        actual_charges = df['total_charges'].astype(float).sum()
        expected_charges = control_totals.sum_total_charges

        # Allow small floating point tolerance (0.01 cents)
        if abs(actual_charges - expected_charges) > 0.01:
            errors.append({
                "code": "E500",
                "severity": "error",
                "type": "charges_mismatch",
                "field": "total_charges",
                "row": "All",
                "message": f"Total charges mismatch - Expected: ${expected_charges:,.2f}, Actual: ${actual_charges:,.2f}, Difference: ${abs(actual_charges - expected_charges):,.2f}",
                "action": "Verify charge calculations and recompute control totals"
            })

    if 'total_payment_received' in df.columns:
        actual_payments = df['total_payment_received'].astype(float).sum()
        expected_payments = control_totals.sum_total_payment_received

        if abs(actual_payments - expected_payments) > 0.01:
            errors.append({
                "code": "E500",
                "severity": "error",
                "type": "payments_mismatch",
                "field": "total_payment_received",
                "row": "All",
                "message": f"Total payments mismatch - Expected: ${expected_payments:,.2f}, Actual: ${actual_payments:,.2f}, Difference: ${abs(actual_payments - expected_payments):,.2f}",
                "action": "Verify payment calculations and recompute control totals"
            })

    # 4. Check for suspiciously high uncompensated care
    if 'total_charges' in df.columns and 'total_payment_received' in df.columns:
        total_charges = df['total_charges'].astype(float).sum()
        total_payments = df['total_payment_received'].astype(float).sum()

        if total_charges > 0:
            uncompensated_ratio = (total_charges - total_payments) / total_charges

            # Warn if >95% uncompensated (might indicate data issue)
            if uncompensated_ratio > 0.95:
                warnings.append({
                    "code": "W200",
                    "severity": "warning",
                    "type": "high_uncompensated_ratio",
                    "field": "total_payment_received",
                    "row": "All",
                    "message": f"High uncompensated care ratio: {uncompensated_ratio*100:.1f}% (${(total_charges-total_payments):,.2f} of ${total_charges:,.2f})",
                    "action": "Review payment data - this is unusually high"
                })

    # 5. Check for negative financial values
    if 'total_charges' in df.columns:
        try:
            charges_numeric = pd.to_numeric(df['total_charges'], errors='coerce')
            negative_charges = df[charges_numeric < 0]
            if len(negative_charges) > 0:
                warnings.append({
                    "code": "W201",
                    "severity": "warning",
                    "type": "negative_charges",
                    "field": "total_charges",
                    "row": "Multiple",
                    "message": f"Found {len(negative_charges)} records with negative charges",
                    "action": "Review records - negative charges may indicate refunds or corrections",
                    "affected_rows": list(negative_charges.index)
                })
        except Exception:
            pass  # Skip if type conversion fails

    if 'total_payment_received' in df.columns:
        try:
            payments_numeric = pd.to_numeric(df['total_payment_received'], errors='coerce')
            negative_payments = df[payments_numeric < 0]
            if len(negative_payments) > 0:
                warnings.append({
                    "code": "W202",
                    "severity": "warning",
                    "type": "negative_payments",
                    "field": "total_payment_received",
                    "row": "Multiple",
                    "message": f"Found {len(negative_payments)} records with negative payments",
                    "action": "Review records - negative payments may indicate refunds or chargebacks",
                    "affected_rows": list(negative_payments.index)
                })
        except Exception:
            pass  # Skip if type conversion fails

    # 6. Validate period boundaries (date range sanity)
    if 'visit_date' in df.columns:
        try:
            dates = pd.to_datetime(df['visit_date'], errors='coerce')
            valid_dates = dates.dropna()

            if len(valid_dates) > 0:
                min_date = valid_dates.min()
                max_date = valid_dates.max()
                date_span = (max_date - min_date).days

                # Warn if date span exceeds 2 years (unusual for single submission)
                if date_span > 730:
                    warnings.append({
                        "code": "W400",
                        "severity": "warning",
                        "type": "wide_date_range",
                        "field": "visit_date",
                        "row": "All",
                        "message": f"Date range spans {date_span} days ({min_date.date()} to {max_date.date()}) - typically submissions cover shorter periods",
                        "action": "Verify date range is correct for this reporting period"
                    })

                # Check for future dates
                from datetime import datetime
                today = datetime.now()
                future_dates = df[dates > today]
                if len(future_dates) > 0:
                    warnings.append({
                        "code": "W401",
                        "severity": "warning",
                        "type": "future_dates",
                        "field": "visit_date",
                        "row": "Multiple",
                        "message": f"Found {len(future_dates)} records with future visit dates",
                        "action": "Verify dates are correct - future dates may be scheduling errors",
                        "affected_rows": list(future_dates.index)
                    })
        except Exception as e:
            # Don't fail validation on date parsing errors (already caught in field validation)
            pass

    # 7. Check payor distribution (warn if 100% one payor - unusual)
    if 'payor_source' in df.columns:
        payor_counts = df['payor_source'].value_counts()
        if len(payor_counts) == 1 and len(df) > 10:
            single_payor = payor_counts.index[0]
            warnings.append({
                "code": "W300",
                "severity": "warning",
                "type": "single_payor_only",
                "field": "payor_source",
                "row": "All",
                "message": f"All {len(df)} records have same payor source: '{single_payor}'",
                "action": "Verify payor data - single payor for all records is unusual"
            })

    # Generate result
    passed = len(errors) == 0
    return ValidationResult(
        passed=passed,
        errors=errors,
        warnings=warnings,
        row_count=len(df),
        error_count=len(errors),
        warning_count=len(warnings)
    )


def validate_duplicate_records(df: pd.DataFrame, id_column: str = 'record_id') -> Tuple[List[Dict], List[Dict]]:
    """
    Check for duplicate record IDs.

    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []

    if id_column not in df.columns:
        warnings.append({
            "code": "W600",
            "severity": "warning",
            "type": "missing_id_column",
            "field": id_column,
            "row": "All",
            "message": f"Column '{id_column}' not found - cannot check for duplicates",
            "action": "Add unique ID column to enable duplicate detection"
        })
        return errors, warnings

    # Find duplicates
    duplicates = df[df.duplicated(subset=[id_column], keep=False)]

    if len(duplicates) > 0:
        duplicate_ids = duplicates[id_column].unique()
        errors.append({
            "code": "E300",
            "severity": "error",
            "type": "duplicate_record_id",
            "field": id_column,
            "row": "Multiple",
            "message": f"Found {len(duplicate_ids)} duplicate {id_column} values affecting {len(duplicates)} total records",
            "action": f"Remove duplicate records or ensure each {id_column} is unique",
            "duplicate_ids": list(map(str, duplicate_ids[:10]))  # Show first 10
        })

    return errors, warnings
