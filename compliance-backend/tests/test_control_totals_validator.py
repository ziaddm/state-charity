# tests/test_control_totals_validator.py
"""
Unit tests for control totals validator.

Tests cross-record validation:
- Duplicate record IDs
- Control totals reconciliation
- Financial validation (charges, payments)
- Date range checks
- Payor distribution analysis
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from app.validation.control_totals_validator import (
    validate_control_totals,
    validate_duplicate_records
)
from app.models.artifacts import ControlTotals


class TestDuplicateDetection:
    """Test duplicate record ID detection"""

    def test_no_duplicates(self):
        """Test dataframe with no duplicates passes"""
        df = pd.DataFrame({
            "record_id": ["R001", "R002", "R003"]
        })

        errors, warnings = validate_duplicate_records(df, "record_id")

        assert len(errors) == 0
        assert len(warnings) == 0

    def test_duplicate_records_detected(self):
        """Test duplicate record IDs are detected"""
        df = pd.DataFrame({
            "record_id": ["R001", "R002", "R001", "R003", "R002"]  # R001 and R002 duplicated
        })

        errors, warnings = validate_duplicate_records(df, "record_id")

        assert len(errors) == 1
        assert errors[0]["code"] == "E300"
        assert errors[0]["type"] == "duplicate_record_id"
        assert "2 duplicate" in errors[0]["message"]

    def test_missing_id_column_warning(self):
        """Test warning when ID column doesn't exist"""
        df = pd.DataFrame({
            "other_field": ["A", "B"]
        })

        errors, warnings = validate_duplicate_records(df, "record_id")

        assert len(warnings) == 1
        assert warnings[0]["code"] == "W600"


class TestControlTotalsValidation:
    """Test control totals validation logic"""

    def test_valid_control_totals(self):
        """Test validation passes with correct control totals"""
        df = pd.DataFrame({
            "record_id": ["R001", "R002"],
            "total_charges": ["1000.00", "2000.00"],
            "total_payment_received": ["800.00", "1500.00"]
        })

        control_totals = ControlTotals(
            row_count=2,
            sum_total_charges=3000.00,
            sum_total_payment_received=2300.00,
            by_payor_source={},
            by_claim_type={}
        )

        result = validate_control_totals(df, control_totals, "NJ")

        assert result.passed is True
        assert result.error_count == 0

    def test_row_count_mismatch(self):
        """Test error when row count doesn't match"""
        df = pd.DataFrame({
            "record_id": ["R001", "R002", "R003"]  # 3 rows
        })

        control_totals = ControlTotals(
            row_count=2,  # Claims 2 rows but df has 3
            sum_total_charges=0,
            sum_total_payment_received=0,
            by_payor_source={},
            by_claim_type={}
        )

        result = validate_control_totals(df, control_totals, "NJ")

        assert result.passed is False
        assert any(e["type"] == "row_count_mismatch" for e in result.errors)

    def test_charges_mismatch(self):
        """Test error when total charges don't reconcile"""
        df = pd.DataFrame({
            "record_id": ["R001", "R002"],
            "total_charges": ["1000.00", "2000.00"]  # Sum = 3000
        })

        control_totals = ControlTotals(
            row_count=2,
            sum_total_charges=3500.00,  # Wrong total
            sum_total_payment_received=0,
            by_payor_source={},
            by_claim_type={}
        )

        result = validate_control_totals(df, control_totals, "NJ")

        assert result.passed is False
        assert any(e["type"] == "charges_mismatch" for e in result.errors)

    def test_payments_mismatch(self):
        """Test error when total payments don't reconcile"""
        df = pd.DataFrame({
            "record_id": ["R001", "R002"],
            "total_payment_received": ["800.00", "1500.00"]  # Sum = 2300
        })

        control_totals = ControlTotals(
            row_count=2,
            sum_total_charges=0,
            sum_total_payment_received=2000.00,  # Wrong total
            by_payor_source={},
            by_claim_type={}
        )

        result = validate_control_totals(df, control_totals, "NJ")

        assert result.passed is False
        assert any(e["type"] == "payments_mismatch" for e in result.errors)

    def test_floating_point_tolerance(self):
        """Test small floating point differences are tolerated"""
        df = pd.DataFrame({
            "record_id": ["R001"],
            "total_charges": ["1000.001"]  # Tiny floating point difference
        })

        control_totals = ControlTotals(
            row_count=1,
            sum_total_charges=1000.00,  # Slightly different
            sum_total_payment_received=0,
            by_payor_source={},
            by_claim_type={}
        )

        result = validate_control_totals(df, control_totals, "NJ")

        # Should pass - difference is within 0.01 tolerance
        assert result.passed is True

    def test_high_uncompensated_care_warning(self):
        """Test warning for unusually high uncompensated care ratio"""
        df = pd.DataFrame({
            "record_id": ["R001", "R002"],
            "total_charges": ["10000.00", "20000.00"],  # Total: 30000
            "total_payment_received": ["500.00", "500.00"]  # Total: 1000 (96.7% uncompensated)
        })

        control_totals = ControlTotals(
            row_count=2,
            sum_total_charges=30000.00,
            sum_total_payment_received=1000.00,
            by_payor_source={},
            by_claim_type={}
        )

        result = validate_control_totals(df, control_totals, "NJ")

        # Should have warning for high uncompensated ratio
        assert any(w["type"] == "high_uncompensated_ratio" for w in result.warnings)

    def test_negative_charges_warning(self):
        """Test warning for negative charge values"""
        df = pd.DataFrame({
            "record_id": ["R001", "R002"],
            "total_charges": ["-500.00", "1000.00"]  # First row has negative charge
        })

        control_totals = ControlTotals(
            row_count=2,
            sum_total_charges=500.00,
            sum_total_payment_received=0,
            by_payor_source={},
            by_claim_type={}
        )

        result = validate_control_totals(df, control_totals, "NJ")

        # Should have warning for negative charges
        assert any(w["type"] == "negative_charges" for w in result.warnings)

    def test_negative_payments_warning(self):
        """Test warning for negative payment values"""
        df = pd.DataFrame({
            "record_id": ["R001", "R002"],
            "total_payment_received": ["-200.00", "500.00"]  # Negative payment
        })

        control_totals = ControlTotals(
            row_count=2,
            sum_total_charges=0,
            sum_total_payment_received=300.00,
            by_payor_source={},
            by_claim_type={}
        )

        result = validate_control_totals(df, control_totals, "NJ")

        # Should have warning for negative payments
        assert any(w["type"] == "negative_payments" for w in result.warnings)


class TestDateRangeValidation:
    """Test date range and period boundary checks"""

    def test_normal_date_range(self):
        """Test normal date range (< 2 years) passes without warning"""
        today = datetime.now()
        df = pd.DataFrame({
            "record_id": ["R001", "R002"],
            "visit_date": [
                (today - timedelta(days=30)).strftime("%Y-%m-%d"),
                (today - timedelta(days=60)).strftime("%Y-%m-%d")
            ]
        })

        control_totals = ControlTotals(
            row_count=2,
            sum_total_charges=0,
            sum_total_payment_received=0,
            by_payor_source={},
            by_claim_type={}
        )

        result = validate_control_totals(df, control_totals, "NJ")

        # Should not have wide date range warning
        assert not any(w["type"] == "wide_date_range" for w in result.warnings)

    def test_wide_date_range_warning(self):
        """Test warning for date range > 2 years"""
        today = datetime.now()
        df = pd.DataFrame({
            "record_id": ["R001", "R002"],
            "visit_date": [
                (today - timedelta(days=800)).strftime("%Y-%m-%d"),  # Over 2 years ago
                today.strftime("%Y-%m-%d")
            ]
        })

        control_totals = ControlTotals(
            row_count=2,
            sum_total_charges=0,
            sum_total_payment_received=0,
            by_payor_source={},
            by_claim_type={}
        )

        result = validate_control_totals(df, control_totals, "NJ")

        # Should have wide date range warning
        assert any(w["type"] == "wide_date_range" for w in result.warnings)

    def test_future_dates_warning(self):
        """Test warning for future visit dates"""
        today = datetime.now()
        df = pd.DataFrame({
            "record_id": ["R001", "R002"],
            "visit_date": [
                today.strftime("%Y-%m-%d"),
                (today + timedelta(days=30)).strftime("%Y-%m-%d")  # Future date
            ]
        })

        control_totals = ControlTotals(
            row_count=2,
            sum_total_charges=0,
            sum_total_payment_received=0,
            by_payor_source={},
            by_claim_type={}
        )

        result = validate_control_totals(df, control_totals, "NJ")

        # Should have future dates warning
        assert any(w["type"] == "future_dates" for w in result.warnings)


class TestPayorDistribution:
    """Test payor source distribution checks"""

    def test_diverse_payor_distribution(self):
        """Test multiple payor sources don't trigger warning"""
        df = pd.DataFrame({
            "record_id": ["R001", "R002", "R003"],
            "payor_source": ["Medicaid", "Medicare", "Uninsured"]
        })

        control_totals = ControlTotals(
            row_count=3,
            sum_total_charges=0,
            sum_total_payment_received=0,
            by_payor_source={},
            by_claim_type={}
        )

        result = validate_control_totals(df, control_totals, "NJ")

        # Should not have single payor warning
        assert not any(w["type"] == "single_payor_only" for w in result.warnings)

    def test_single_payor_warning(self):
        """Test warning when all records have same payor"""
        df = pd.DataFrame({
            "record_id": [f"R{i:03d}" for i in range(15)],  # 15 records
            "payor_source": ["Medicaid"] * 15  # All same payor
        })

        control_totals = ControlTotals(
            row_count=15,
            sum_total_charges=0,
            sum_total_payment_received=0,
            by_payor_source={},
            by_claim_type={}
        )

        result = validate_control_totals(df, control_totals, "NJ")

        # Should have single payor warning
        assert any(w["type"] == "single_payor_only" for w in result.warnings)

    def test_single_payor_small_file_no_warning(self):
        """Test single payor in small file (<=10 rows) doesn't warn"""
        df = pd.DataFrame({
            "record_id": ["R001", "R002"],  # Only 2 records
            "payor_source": ["Medicaid", "Medicaid"]
        })

        control_totals = ControlTotals(
            row_count=2,
            sum_total_charges=0,
            sum_total_payment_received=0,
            by_payor_source={},
            by_claim_type={}
        )

        result = validate_control_totals(df, control_totals, "NJ")

        # Should not warn for small files
        assert not any(w["type"] == "single_payor_only" for w in result.warnings)


# Pytest configuration
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
