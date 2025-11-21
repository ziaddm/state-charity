import pandas as pd
from typing import List, Dict, Any
from datetime import datetime
from app.models.artifacts import ValidationResult
from app.schema.nj_schema import CANONICAL_VISITS_SCHEMA, CROSS_FIELD_RULES
from app.validation.coercions import apply_coercions

# Validation severity defaults - pragmatic approach for healthcare data
# Philosophy: Only block submission for catastrophic issues that would cause state rejection
VALIDATION_DEFAULTS = {
    "required_missing": "error",       # Always error - critical field missing
    "too_long": "error",              # Always error - breaks fixed-width output
    "too_short": "warning",           # Warning - might be incomplete but not blocking
    "invalid_enum": "warning",        # WARNING (changed from error) - might be new valid code
    "below_min": "warning",           # WARNING (changed from error) - might be edge case
    "above_max": "warning",           # WARNING (changed from error) - might be edge case
    "invalid_type": "error",          # Error - breaks processing
    "unparseable_date": "error",      # Error - breaks processing
    "cross_field_violation": "error", # Default error, but can override per rule
}

def _validate_field(field_name, value, field_spec, row_num):
    """
    Validate a single field value against its schema specification.
    Returns tuple of (errors, warnings) lists where each issue has:
    - code: error/warning code (e.g., E001, W001)
    - severity: 'error' or 'warning'
    - field: field name
    - row: row number
    - message: human-readable message
    - value: the problematic value (optional)
    """
    errors = []
    warnings = []

    # check required
    if field_spec.get("required", False) and (value is None or value == ""):
        errors.append({
            "code": "E001",
            "severity": "error",
            "type": "required_missing",
            "field": field_name,
            "row": row_num,
            "message": f"Required field '{field_name}' is empty - Provide a value for this field",
            "action": f"Fill in {field_name} for row {row_num}"
        })
        return errors, warnings

    # Check warn_if_missing for optional fields
    if field_spec.get("warn_if_missing", False) and (value is None or value == ""):
        warnings.append({
            "code": "W002",
            "severity": "warning",
            "type": "recommended_missing",
            "field": field_name,
            "row": row_num,
            "message": f"Recommended field '{field_name}' is empty - Consider adding data for better reporting quality",
            "action": f"Add {field_name} value if available"
        })
        return errors, warnings

    if value is None or value == "":
        return errors, warnings

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
            # Length too short is a warning unless it's required
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

    # Check enum - now warning by default (might be new valid code)
    if "enum" in field_spec:
        allowed_values = field_spec["enum"]
        if value not in allowed_values:
            # Allow field-level severity override, otherwise use default
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

    # Check bounds (for numbers) - now warning by default (might be edge case)
    bounds = field_spec.get("bounds", {})
    if bounds:
        try:
            num_value = float(value) if isinstance(value, (int, float, str)) else value
            if "min" in bounds and num_value < bounds["min"]:
                # Allow field-level severity override, otherwise use default
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
                # Allow field-level severity override, otherwise use default
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

    return errors, warnings

def _validate_cross_field_rules(df: pd.DataFrame, rules: List[Dict[str, Any]]) -> tuple:
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

        # Parse the rule expression
        # Supported formats:
        # - "field1 <= field2"
        # - "field1 >= field2"
        # - "field1 < field2"
        # - "field1 > field2"
        # - "field1 == field2"
        # - "field1 != field2"

        try:
            # Simple parser for comparison rules
            operators = ["<=", ">=", "==", "!=", "<", ">"]
            operator = None
            for op in operators:
                if op in rule_expr:
                    operator = op
                    break

            if not operator:
                continue  # Skip rules we can't parse

            parts = rule_expr.split(operator)
            if len(parts) != 2:
                continue

            field1 = parts[0].strip()
            field2 = parts[1].strip()

            # Check if both fields exist
            if field1 not in df.columns or field2 not in df.columns:
                continue

            # Perform validation row by row
            for idx in df.index:
                val1 = df.loc[idx, field1]
                val2 = df.loc[idx, field2]

                # Skip if either value is None or empty
                if pd.isna(val1) or pd.isna(val2):
                    continue
                if val1 == "" or val2 == "":
                    continue

                # Convert to comparable types
                try:
                    # Try numeric comparison first
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
                        message = f"Cross-field rule violated: {field1}={val1} {operator} {field2}={val2}"
                        issue = {
                            "code": "E100" if on_fail == "error" else "W100",
                            "severity": "error" if on_fail == "error" else "warning",
                            "type": "cross_field_violation",
                            "rule": rule_expr,
                            "row": idx,
                            "field": f"{field1}, {field2}",
                            "fields": [field1, field2],
                            "values": {field1: val1, field2: val2},
                            "message": message
                        }

                        if on_fail == "error":
                            errors.append(issue)
                        else:
                            warnings.append(issue)

                except (ValueError, TypeError):
                    # If not numeric, try string/date comparison
                    try:
                        # Try date comparison
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
                                message = f"Cross-field rule violated: {field1}={val1} {operator} {field2}={val2}"
                                issue = {
                                    "code": "E100" if on_fail == "error" else "W100",
                                    "severity": "error" if on_fail == "error" else "warning",
                                    "type": "cross_field_violation",
                                    "rule": rule_expr,
                                    "row": idx,
                                    "field": f"{field1}, {field2}",
                                    "fields": [field1, field2],
                                    "values": {field1: str(val1), field2: str(val2)},
                                    "message": message
                                }

                                if on_fail == "error":
                                    errors.append(issue)
                                else:
                                    warnings.append(issue)
                    except:
                        # String comparison as fallback
                        pass

        except Exception as e:
            # Log parsing/validation errors but don't fail validation
            pass

    return errors, warnings

def validate_canonical(df: pd.DataFrame, state_code: str) -> ValidationResult:
    """
    Validate canonical dataframe against schema rules.
    Returns ValidationResult with errors and warnings.

    Per MVP spec section 5.3:
    - Errors: block submission, must be corrected
    - Warnings: flagged, operator acknowledgment required
    - Each event carries code, severity, message, field reference
    """

    errors = []
    warnings = []

    # Applying coercions
    df_coerced = apply_coercions(df, CANONICAL_VISITS_SCHEMA)

    # Validate each field for each row
    for field_name, field_spec in CANONICAL_VISITS_SCHEMA.items():
        if field_name not in df_coerced.columns:
            continue
        for idx, value in df_coerced[field_name].items():
            field_errors, field_warnings = _validate_field(field_name, value, field_spec, idx)
            errors.extend(field_errors)
            warnings.extend(field_warnings)

    # Cross-field validation
    cross_field_errors, cross_field_warnings = _validate_cross_field_rules(
        df_coerced,
        CROSS_FIELD_RULES
    )
    errors.extend(cross_field_errors)
    warnings.extend(cross_field_warnings)

    # Generate result - passed if no errors (warnings don't block submission)
    passed = len(errors) == 0
    return ValidationResult(
        passed=passed,
        errors=errors,
        warnings=warnings,
        row_count=len(df_coerced),
        error_count=len(errors),
        warning_count=len(warnings)
    )

