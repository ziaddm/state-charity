# tests/test_pre_validator.py
"""
Unit tests for pre-validator.

Tests raw structure validation before mapping:
- Missing required source columns
- Missing optional source columns
- Empty files
- Unmapped extra columns
"""

import pytest
import pandas as pd
from app.validation.pre_validator import validate_raw_structure


class MockTenantMapper:
    """Mock tenant mapper for testing"""
    def __init__(self, field_map, constants=None):
        self.field_map = field_map
        self.constants = constants or {}


class TestPreValidator:
    """Test pre-validation of raw input structure"""

    def test_valid_structure_all_columns_present(self):
        """Test validation passes when all required columns present"""
        df_raw = pd.DataFrame({
            "__rownum": [1, 2],
            "Patient ID": ["P001", "P002"],
            "Visit Date": ["2024-01-01", "2024-01-02"]
        })

        mapper = MockTenantMapper({
            "Patient ID": "patient_id",
            "Visit Date": "visit_date"
        })

        result = validate_raw_structure(df_raw, mapper, "NJ")

        assert result.passed is True
        assert result.error_count == 0

    def test_missing_required_source_column(self):
        """Test error when required source column is missing"""
        df_raw = pd.DataFrame({
            "__rownum": [1, 2],
            "Visit Date": ["2024-01-01", "2024-01-02"]
            # Missing "Patient ID" which maps to required canonical field
        })

        mapper = MockTenantMapper({
            "Patient ID": "patient_id",  # patient_id is required in schema
            "Visit Date": "visit_date"
        })

        result = validate_raw_structure(df_raw, mapper, "NJ")

        # Should error for missing Patient ID
        assert result.passed is False
        assert result.error_count >= 1

        # Check error details
        error = next(e for e in result.errors if e["code"] == "E500")
        assert "Patient ID" in error["message"]

    def test_missing_optional_source_column_warning(self):
        """Test warning when optional source column is missing"""
        df_raw = pd.DataFrame({
            "__rownum": [1, 2],
            "Patient ID": ["P001", "P002"]
            # Missing optional column
        })

        mapper = MockTenantMapper({
            "Patient ID": "patient_id",
            "Optional Field": "optional_canonical_field"
        })

        result = validate_raw_structure(df_raw, mapper, "NJ")

        # Should still pass (only warnings)
        assert result.passed is True
        assert result.warning_count >= 1

    def test_missing_column_with_constant_fallback(self):
        """Test missing column with constant fallback doesn't error"""
        df_raw = pd.DataFrame({
            "__rownum": [1, 2],
            "Patient ID": ["P001", "P002"]
            # Missing "Facility Code" but has constant
        })

        mapper = MockTenantMapper(
            field_map={
                "Patient ID": "patient_id",
                "Facility Code": "facility_code"
            },
            constants={
                "facility_code": "ACME_HEALTH"  # Constant fallback
            }
        )

        result = validate_raw_structure(df_raw, mapper, "NJ")

        # Should not error because constant provides value
        assert result.passed is True

    def test_unmapped_columns_generate_warnings(self):
        """Test that extra columns in source generate info warnings"""
        df_raw = pd.DataFrame({
            "__rownum": [1, 2],
            "Patient ID": ["P001", "P002"],
            "Extra Column 1": ["A", "B"],
            "Extra Column 2": ["X", "Y"]
        })

        mapper = MockTenantMapper({
            "Patient ID": "patient_id"
            # Extra Column 1 and 2 are not mapped
        })

        result = validate_raw_structure(df_raw, mapper, "NJ")

        # Should pass but have warnings for unmapped columns
        assert result.passed is True
        assert result.warning_count >= 2

        # Check for info messages about unmapped columns
        unmapped_warnings = [w for w in result.warnings if w["code"] == "I003"]
        assert len(unmapped_warnings) == 2

    def test_empty_file_error(self):
        """Test error when file has no data rows"""
        df_raw = pd.DataFrame()  # Empty dataframe

        mapper = MockTenantMapper({
            "Patient ID": "patient_id"
        })

        result = validate_raw_structure(df_raw, mapper, "NJ")

        assert result.passed is False
        assert result.error_count >= 1

        # Check for empty file error
        empty_error = next(e for e in result.errors if e["type"] == "empty_file")
        assert "empty" in empty_error["message"].lower()

    def test_rownum_column_ignored(self):
        """Test that __rownum column is ignored in unmapped column checks"""
        df_raw = pd.DataFrame({
            "__rownum": [1, 2],
            "Patient ID": ["P001", "P002"]
        })

        mapper = MockTenantMapper({
            "Patient ID": "patient_id"
        })

        result = validate_raw_structure(df_raw, mapper, "NJ")

        # __rownum should not trigger unmapped column warning
        unmapped_warnings = [w for w in result.warnings if w["code"] == "I003"]
        assert len(unmapped_warnings) == 0

    def test_multiple_missing_required_columns(self):
        """Test multiple missing required columns all reported"""
        df_raw = pd.DataFrame({
            "__rownum": [1, 2]
            # Missing both required columns
        })

        mapper = MockTenantMapper({
            "Patient ID": "patient_id",  # Required
            "Visit Date": "visit_date"   # Required
        })

        result = validate_raw_structure(df_raw, mapper, "NJ")

        assert result.passed is False
        # Should have error for each missing required column
        assert result.error_count >= 2


# Pytest configuration
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
