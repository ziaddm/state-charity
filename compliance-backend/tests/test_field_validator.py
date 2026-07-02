# tests/test_field_validator.py
"""
Unit tests for field validator.

Tests all validation logic:
- Required field checks
- Length validation (min/max)
- Enum validation
- Numeric bounds validation
- Cross-field rules
"""

import pytest
import pandas as pd
from app.validation.field_validator import (
    validate_canonical_fields,
    _validate_field,
    _validate_cross_field_rules
)


class TestFieldValidation:
    """Test individual field validation logic"""

    def test_required_field_missing(self):
        """Test that missing required fields generate errors"""
        field_spec = {"required": True}
        errors, warnings, info = _validate_field("patient_id", "", field_spec, row_num=1)

        assert len(errors) == 1
        assert errors[0]["code"] == "E001"
        assert errors[0]["severity"] == "error"
        assert "patient_id" in errors[0]["message"]

    def test_required_field_present(self):
        """Test that present required fields pass"""
        field_spec = {"required": True}
        errors, warnings, info = _validate_field("patient_id", "12345", field_spec, row_num=1)

        assert len(errors) == 0
        assert len(warnings) == 0

    def test_warn_if_missing(self):
        """warn_if_missing produces a non-blocking informational notice"""
        field_spec = {"warn_if_missing": True}
        errors, warnings, info = _validate_field("optional_field", "", field_spec, row_num=1)

        assert len(errors) == 0
        assert len(warnings) == 0
        assert len(info) == 1
        assert info[0]["code"] == "I002"

    def test_length_max_exceeded(self):
        """Test max length validation"""
        field_spec = {"length": {"max": 5}}
        errors, warnings, info = _validate_field("zip", "123456", field_spec, row_num=1)

        assert len(errors) == 1
        assert errors[0]["code"] == "E002"
        assert "too long" in errors[0]["message"].lower()

    def test_length_max_ok(self):
        """Test value at exactly max length passes"""
        field_spec = {"length": {"max": 5}}
        errors, warnings, info = _validate_field("zip", "12345", field_spec, row_num=1)

        assert len(errors) == 0

    def test_length_min_required_field(self):
        """Test min length on required field generates error"""
        field_spec = {"required": True, "length": {"min": 3}}
        errors, warnings, info = _validate_field("code", "AB", field_spec, row_num=1)

        assert len(errors) == 1
        assert errors[0]["code"] == "E003"

    def test_length_min_optional_field(self):
        """Test min length on optional field generates warning"""
        field_spec = {"required": False, "length": {"min": 3}}
        errors, warnings, info = _validate_field("code", "AB", field_spec, row_num=1)

        assert len(warnings) == 1
        assert warnings[0]["code"] == "W001"

    def test_enum_valid_value(self):
        """Test valid enum value passes"""
        field_spec = {"enum": ["M", "F", "U"]}
        errors, warnings, info = _validate_field("gender", "M", field_spec, row_num=1)

        assert len(errors) == 0
        assert len(warnings) == 0

    def test_enum_invalid_value_warning(self):
        """Test invalid enum generates warning by default"""
        field_spec = {"enum": ["M", "F", "U"]}
        errors, warnings, info = _validate_field("gender", "X", field_spec, row_num=1)

        assert len(warnings) == 1
        assert warnings[0]["code"] == "W004"

    def test_enum_invalid_value_error(self):
        """Test invalid enum can be configured as error"""
        field_spec = {
            "enum": ["A", "B", "C"],
            "severity": {"invalid_enum": "error"}
        }
        errors, warnings, info = _validate_field("category", "D", field_spec, row_num=1)

        assert len(errors) == 1
        assert errors[0]["code"] == "E004"

    def test_bounds_below_min_warning(self):
        """Test value below minimum generates warning by default"""
        field_spec = {"bounds": {"min": 0}}
        errors, warnings, info = _validate_field("charges", -100, field_spec, row_num=1)

        assert len(warnings) == 1
        assert warnings[0]["code"] == "W005"

    def test_bounds_above_max_warning(self):
        """Test value above maximum generates warning by default"""
        field_spec = {"bounds": {"max": 120}}
        errors, warnings, info = _validate_field("age", 150, field_spec, row_num=1)

        assert len(warnings) == 1
        assert warnings[0]["code"] == "W006"

    def test_bounds_within_range(self):
        """Test value within bounds passes"""
        field_spec = {"bounds": {"min": 0, "max": 120}}
        errors, warnings, info = _validate_field("age", 45, field_spec, row_num=1)

        assert len(errors) == 0
        assert len(warnings) == 0

    def test_empty_optional_field(self):
        """Test empty optional field passes without issues"""
        field_spec = {"required": False, "length": {"max": 10}}
        errors, warnings, info = _validate_field("optional", "", field_spec, row_num=1)

        assert len(errors) == 0
        assert len(warnings) == 0


class TestCrossFieldRules:
    """Test cross-field validation rules"""

    def test_numeric_comparison_valid(self):
        """Test valid numeric cross-field rule"""
        df = pd.DataFrame({
            "total_charges": [1000.0, 2000.0],
            "total_payments": [800.0, 1500.0]
        })
        rules = [{"rule": "total_payments <= total_charges", "on_fail": "error"}]

        errors, warnings = _validate_cross_field_rules(df, rules)
        assert len(errors) == 0

    def test_numeric_comparison_violation(self):
        """Test numeric cross-field rule violation"""
        df = pd.DataFrame({
            "total_charges": [1000.0, 2000.0],
            "total_payments": [1200.0, 1500.0]  # First row violates: payment > charges
        })
        rules = [{"rule": "total_payments <= total_charges", "on_fail": "error"}]

        errors, warnings = _validate_cross_field_rules(df, rules)
        assert len(errors) == 1
        assert errors[0]["code"] == "E100"

    def test_date_comparison_valid(self):
        """Test valid date cross-field rule"""
        df = pd.DataFrame({
            "admission_date": ["2024-01-01", "2024-02-01"],
            "discharge_date": ["2024-01-05", "2024-02-03"]
        })
        rules = [{"rule": "admission_date <= discharge_date", "on_fail": "error"}]

        errors, warnings = _validate_cross_field_rules(df, rules)
        assert len(errors) == 0

    def test_date_comparison_violation(self):
        """Test date cross-field rule violation"""
        df = pd.DataFrame({
            "admission_date": ["2024-01-05", "2024-02-01"],
            "discharge_date": ["2024-01-01", "2024-02-03"]  # First row: discharge before admission
        })
        rules = [{"rule": "admission_date <= discharge_date", "on_fail": "error"}]

        errors, warnings = _validate_cross_field_rules(df, rules)
        assert len(errors) == 1

    def test_cross_field_warning_severity(self):
        """Test cross-field rule can be warning instead of error"""
        df = pd.DataFrame({
            "field1": [10, 20],
            "field2": [5, 25]
        })
        rules = [{"rule": "field1 >= field2", "on_fail": "warning"}]

        errors, warnings = _validate_cross_field_rules(df, rules)
        assert len(warnings) == 1
        assert warnings[0]["code"] == "W100"

    def test_cross_field_skips_empty_values(self):
        """Test cross-field rules skip rows with empty values"""
        df = pd.DataFrame({
            "field1": [10, "", 30],
            "field2": [5, 15, 25]
        })
        rules = [{"rule": "field1 >= field2", "on_fail": "error"}]

        errors, warnings = _validate_cross_field_rules(df, rules)
        # Should only validate rows 0 and 2 (row 1 has empty value)
        assert len(errors) == 0


class TestValidateCanonicalFields:
    """Test full canonical field validation"""

    def test_validate_all_fields_pass(self):
        """Test validation with all fields passing"""
        df = pd.DataFrame({
            "patient_id": ["P001", "P002"],
            "age": [45, 67],
            "gender": ["M", "F"]
        })

        schema = {
            "patient_id": {"required": True, "length": {"max": 10}},
            "age": {"required": True, "bounds": {"min": 0, "max": 120}},
            "gender": {"required": True, "enum": ["M", "F", "U"]}
        }

        result = validate_canonical_fields(df, schema, [], "NJ")

        assert result.passed is True
        assert result.error_count == 0
        assert result.warning_count == 0
        assert result.row_count == 2

    def test_validate_multiple_errors(self):
        """Test validation accumulates multiple errors"""
        df = pd.DataFrame({
            "patient_id": ["", "P002"],  # Missing required field
            "age": [45, 150],  # Age too high
            "gender": ["M", "X"]  # Invalid enum
        })

        schema = {
            "patient_id": {"required": True},
            "age": {"bounds": {"max": 120}, "severity": {"above_max": "error"}},
            "gender": {"enum": ["M", "F", "U"], "severity": {"invalid_enum": "error"}}
        }

        result = validate_canonical_fields(df, schema, [], "NJ")

        assert result.passed is False
        assert result.error_count == 3  # Missing patient_id, high age, invalid gender
        assert result.row_count == 2

    def test_validate_with_cross_field_rules(self):
        """Test validation includes cross-field rules"""
        df = pd.DataFrame({
            "total_charges": [1000.0, 2000.0],
            "total_payments": [1200.0, 1500.0]  # First row payment > charges
        })

        schema = {
            "total_charges": {"required": True},
            "total_payments": {"required": True}
        }

        rules = [{"rule": "total_payments <= total_charges", "on_fail": "error"}]

        result = validate_canonical_fields(df, schema, rules, "NJ")

        assert result.passed is False
        assert result.error_count >= 1  # At least the cross-field violation

    def test_validate_skips_missing_columns(self):
        """Test validation skips fields not in dataframe"""
        df = pd.DataFrame({
            "patient_id": ["P001"]
        })

        schema = {
            "patient_id": {"required": True},
            "nonexistent_field": {"required": True}  # This field not in df
        }

        # Should not error on nonexistent_field since it's not in df
        result = validate_canonical_fields(df, schema, [], "NJ")

        # Only validates fields that exist in df
        assert result.passed is True


# Pytest configuration
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
