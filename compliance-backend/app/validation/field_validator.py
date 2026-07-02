# app/validation/field_validator.py
"""
Field validation: Validates mapped canonical field values.

Checks:
- Required fields have values
- Field lengths and formats
- Enum values
- Numeric bounds
- Cross-field rules
"""

import re

import pandas as pd
from typing import List, Dict, Any, Tuple
from app.models.artifacts import ValidationResult
from app.schema.nj_schema import CODESETS


# Validation severity defaults
VALIDATION_DEFAULTS = {
    "required_missing": "error",
    "too_long": "error",
    "too_short": "warning",
    "invalid_enum": "warning",
    "below_min": "warning",
    "above_max": "warning",
    "invalid_type": "error",
    "unparseable_date": "error",
    "cross_field_violation": "error",
}


def _is_empty(value: Any) -> bool:
    """True for None, empty string, and pandas NA/NaN values."""
    if value is None or value == "":
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _resolve_enum(field_spec: Dict[str, Any]):
    """Return the list of allowed values for a field, resolving enum_ref
    against the state CODESETS. Returns None when no enum applies."""
    if "enum" in field_spec:
        return field_spec["enum"]
    ref = field_spec.get("enum_ref")
    if ref:
        codeset = CODESETS.get(ref)
        if isinstance(codeset, dict):
            return list(codeset.keys())
        if isinstance(codeset, (list, tuple, set)):
            return list(codeset)
    return None


def _validate_field(
    field_name: str,
    value: Any,
    field_spec: Dict[str, Any],
    row_num: int
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Validate a single field value against its schema specification.

    Returns:
        Tuple of (errors, warnings, info) lists
    """
    errors = []
    warnings = []
    info = []

    # Check required
    if field_spec.get("required", False) and _is_empty(value):
        errors.append({
            "code": "E001",
            "severity": "error",
            "type": "required_missing",
            "field": field_name,
            "row": row_num,
            "message": f"Required field '{field_name}' is empty - Provide a value for this field",
            "action": f"Fill in {field_name} for row {row_num}"
        })
        return errors, warnings, info

    # An empty optional-but-recommended field is a data quality note, not a
    # format problem — informational only, never blocks.
    if field_spec.get("warn_if_missing", False) and _is_empty(value):
        info.append({
            "code": "I002",
            "severity": "info",
            "type": "recommended_missing",
            "field": field_name,
            "row": row_num,
            "message": f"Recommended field '{field_name}' is empty - Consider adding data for better reporting quality",
            "action": f"Add {field_name} value if available"
        })
        return errors, warnings, info

    if _is_empty(value):
        return errors, warnings, info

    # Check length
    length_spec = field_spec.get("length", {})
    if length_spec:
        value_len = len(str(value))
        if "max" in length_spec and value_len > length_spec["max"]:
            errors.append({
                "code": "E002",
                "severity": "error",
                "type": "too_long",
                "field": field_name,
                "row": row_num,
                "value": str(value),
                "message": f"Value too long in '{field_name}' - Maximum {length_spec['max']} characters (found {value_len})",
                "action": f"Shorten {field_name} to {length_spec['max']} characters or less"
            })
        if "min" in length_spec and value_len < length_spec["min"]:
            issue = {
                "code": "W001" if not field_spec.get("required") else "E003",
                "severity": "warning" if not field_spec.get("required") else "error",
                "type": "too_short",
                "field": field_name,
                "row": row_num,
                "value": str(value),
                "message": f"Value too short in '{field_name}' - Should be at least {length_spec['min']} characters (found {value_len})",
                "action": f"Verify {field_name} is complete"
            }
            if issue["severity"] == "error":
                errors.append(issue)
            else:
                warnings.append(issue)

    # Check enum (literal `enum` or `enum_ref` resolved against state CODESETS)
    allowed_values = _resolve_enum(field_spec)
    if allowed_values is not None:
        if value not in allowed_values:
            severity = field_spec.get("severity", {}).get("invalid_enum", VALIDATION_DEFAULTS["invalid_enum"])
            issue = {
                "code": "W004" if severity == "warning" else "E004",
                "severity": severity,
                "type": "invalid_enum",
                "field": field_name,
                "row": row_num,
                "value": str(value),
                "message": f"Invalid code '{value}' in '{field_name}' - Must be one of: {', '.join(str(v) for v in allowed_values)}",
                "action": f"Change {field_name} to a valid code"
            }
            if severity == "error":
                errors.append(issue)
            else:
                warnings.append(issue)

    # Check pattern (regex the whole value must match, e.g. ZIP format)
    pattern = field_spec.get("pattern")
    if pattern and not re.fullmatch(pattern, str(value)):
        errors.append({
            "code": "E007",
            "severity": "error",
            "type": "invalid_format",
            "field": field_name,
            "row": row_num,
            "value": str(value),
            "message": f"Invalid format in '{field_name}' - Value '{value}' does not match the required format",
            "action": f"Correct {field_name} for row {row_num}"
        })

    # Check bounds (for numbers)
    bounds = field_spec.get("bounds", {})
    if bounds:
        try:
            num_value = float(value) if isinstance(value, (int, float, str)) else value
            if "min" in bounds and num_value < bounds["min"]:
                severity = field_spec.get("severity", {}).get("below_min", VALIDATION_DEFAULTS["below_min"])
                issue = {
                    "code": "W005" if severity == "warning" else "E005",
                    "severity": severity,
                    "type": "below_min",
                    "field": field_name,
                    "row": row_num,
                    "value": num_value,
                    "message": f"Value {num_value} in '{field_name}' is below minimum {bounds['min']} - Verify data is correct",
                    "action": f"Check {field_name} value (minimum allowed: {bounds['min']})"
                }
                if severity == "error":
                    errors.append(issue)
                else:
                    warnings.append(issue)
            if "max" in bounds and num_value > bounds["max"]:
                severity = field_spec.get("severity", {}).get("above_max", VALIDATION_DEFAULTS["above_max"])
                issue = {
                    "code": "W006" if severity == "warning" else "E006",
                    "severity": severity,
                    "type": "above_max",
                    "field": field_name,
                    "row": row_num,
                    "value": num_value,
                    "message": f"Value {num_value} in '{field_name}' is above maximum {bounds['max']} - Verify data is correct",
                    "action": f"Check {field_name} value (maximum allowed: {bounds['max']})"
                }
                if severity == "error":
                    errors.append(issue)
                else:
                    warnings.append(issue)
        except (ValueError, TypeError):
            pass  # Not a number, skip bounds check

    return errors, warnings, info


def _validate_cross_field_rules(
    df: pd.DataFrame,
    rules: List[Dict[str, Any]]
) -> Tuple[List[Dict], List[Dict]]:
    """
    Validate cross-field rules across the dataframe.

    Args:
        df: DataFrame with canonical schema columns
        rules: List of rule dictionaries with 'rule' and 'on_fail' keys

    Returns:
        Tuple of (errors, warnings) lists
    """
    errors = []
    warnings = []

    for rule_spec in rules:
        rule_expr = rule_spec["rule"]
        on_fail = rule_spec.get("on_fail", "error")

        try:
            # Parse simple comparison rules
            operators = ["<=", ">=", "==", "!=", "<", ">"]
            operator = None
            for op in operators:
                if op in rule_expr:
                    operator = op
                    break

            if not operator:
                continue

            parts = rule_expr.split(operator)
            if len(parts) != 2:
                continue

            field1 = parts[0].strip()
            field2 = parts[1].strip()

            if field1 not in df.columns or field2 not in df.columns:
                continue

            # Validate row by row
            for idx in df.index:
                val1 = df.loc[idx, field1]
                val2 = df.loc[idx, field2]

                if pd.isna(val1) or pd.isna(val2) or val1 == "" or val2 == "":
                    continue

                try:
                    # Try numeric comparison
                    num1 = float(val1)
                    num2 = float(val2)

                    violation = False
                    if operator == "<=":
                        violation = not (num1 <= num2)
                    elif operator == ">=":
                        violation = not (num1 >= num2)
                    elif operator == "<":
                        violation = not (num1 < num2)
                    elif operator == ">":
                        violation = not (num1 > num2)
                    elif operator == "==":
                        violation = not (num1 == num2)
                    elif operator == "!=":
                        violation = not (num1 != num2)

                    if violation:
                        message = f"Data mismatch: {field1} ({val1}) should be {operator} {field2} ({val2}) - Verify these values are correct"
                        issue = {
                            "code": "E100" if on_fail == "error" else "W100",
                            "severity": "error" if on_fail == "error" else "warning",
                            "type": "cross_field_violation",
                            "rule": rule_expr,
                            "row": idx,
                            "field": f"{field1}, {field2}",
                            "message": message,
                            "action": f"Check {field1} and {field2} values for row {idx}"
                        }

                        if on_fail == "error":
                            errors.append(issue)
                        else:
                            warnings.append(issue)

                except (ValueError, TypeError):
                    # Try date comparison
                    try:
                        if "date" in field1.lower() or "date" in field2.lower():
                            date1 = pd.to_datetime(val1)
                            date2 = pd.to_datetime(val2)

                            violation = False
                            if operator == "<=":
                                violation = not (date1 <= date2)
                            elif operator == ">=":
                                violation = not (date1 >= date2)
                            elif operator == "<":
                                violation = not (date1 < date2)
                            elif operator == ">":
                                violation = not (date1 > date2)
                            elif operator == "==":
                                violation = not (date1 == date2)
                            elif operator == "!=":
                                violation = not (date1 != date2)

                            if violation:
                                message = f"Date mismatch: {field1} ({val1}) should be {operator} {field2} ({val2}) - Verify dates are correct"
                                issue = {
                                    "code": "E100" if on_fail == "error" else "W100",
                                    "severity": "error" if on_fail == "error" else "warning",
                                    "type": "cross_field_violation",
                                    "rule": rule_expr,
                                    "row": idx,
                                    "field": f"{field1}, {field2}",
                                    "message": message,
                                    "action": f"Check {field1} and {field2} dates for row {idx}"
                                }

                                if on_fail == "error":
                                    errors.append(issue)
                                else:
                                    warnings.append(issue)
                    except:
                        pass

        except Exception:
            pass

    return errors, warnings


def validate_canonical_fields(
    df: pd.DataFrame,
    schema: Dict[str, Any],
    cross_field_rules: List[Dict[str, Any]],
    state_code: str
) -> ValidationResult:
    """
    Validate canonical dataframe field values against schema.

    Args:
        df: DataFrame with canonical schema columns (after mapping and coercion)
        schema: Canonical schema definition
        cross_field_rules: List of cross-field validation rules
        state_code: Target state code

    Returns:
        ValidationResult with field-level errors and warnings
    """
    errors = []
    warnings = []
    info = []

    # Validate each field for each row
    for field_name, field_spec in schema.items():
        if field_name not in df.columns:
            continue
        for idx, value in df[field_name].items():
            field_errors, field_warnings, field_info = _validate_field(field_name, value, field_spec, idx)
            errors.extend(field_errors)
            warnings.extend(field_warnings)
            info.extend(field_info)

    # Cross-field validation
    cross_field_errors, cross_field_warnings = _validate_cross_field_rules(df, cross_field_rules)
    errors.extend(cross_field_errors)
    warnings.extend(cross_field_warnings)

    # Generate result
    passed = len(errors) == 0
    return ValidationResult(
        passed=passed,
        errors=errors,
        warnings=warnings,
        info=info,
        row_count=len(df),
        error_count=len(errors),
        warning_count=len(warnings),
        info_count=len(info)
    )
