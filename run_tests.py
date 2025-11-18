#!/usr/bin/env python
"""
Quick test runner for compliance analytics pipeline
Run with: python run_tests.py
"""

import subprocess
import sys
import os
from pathlib import Path
import json

def run_command(cmd, description):
    """Run a command and print results."""
    print(f"\n{'='*60}")
    print(f"TEST: {description}")
    print(f"{'='*60}")
    print(f"Command: {cmd}\n")

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    return result.returncode == 0

def main():
    print("Compliance Analytics - Test Suite")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Basic end-to-end
    if run_command(
        "python -m app.main acme_health NJ test_data/acme_health_sample.csv --output-dir test_output",
        "Basic End-to-End Pipeline"
    ):
        tests_passed += 1

        # Check artifacts were created
        output_dir = Path("test_output/acme_health")
        if output_dir.exists():
            runs = list(output_dir.glob("acme_health_NJ_*"))
            if runs:
                latest_run = max(runs, key=lambda p: p.stat().st_mtime)
                print(f"\n[OK] Artifacts created in: {latest_run}")

                # Check files
                artifacts = list(latest_run.glob("*.json"))
                submission_files = list(latest_run.glob("*.txt"))

                print(f"   - JSON artifacts: {len(artifacts)}")
                print(f"   - Submission file: {len(submission_files)}")

                # Show control totals
                control_totals = list(latest_run.glob("*control_totals.json"))
                if control_totals:
                    with open(control_totals[0]) as f:
                        ct = json.load(f)
                        print(f"\n   Control Totals:")
                        print(f"   - Records: {ct['row_count']}")
                        print(f"   - Total Charges: ${ct['sum_total_charges']:.2f}")
                        print(f"   - Total Payments: ${ct['sum_total_payment_received']:.2f}")
                        print(f"   - By Payer: {ct['by_payor_source']}")
    else:
        tests_failed += 1
        print("Test failed")

    # Test 2: Component testing
    print(f"\n{'='*60}")
    print("TEST: Individual Component Tests")
    print(f"{'='*60}\n")

    try:
        # Test extractor
        from app.extraction.extractor import load_source
        df, meta = load_source("test_data/acme_health_sample.csv")
        print(f"Extractor: Loaded {len(df)} rows, {len(df.columns)} columns")
        print(f"Encoding: {meta['encoding']}, Format: {meta['fmt']}")

        # Test mapper
        from app.mapping.mapper import load_tenant_config
        mapper = load_tenant_config("acme_health", "config/tenants")
        df_canonical, warnings = mapper.map_dataframe(df)
        print(f"Mapper: {len(df_canonical.columns)} canonical fields, {len(warnings)} warnings")

        # Test validator
        from app.validation.validator import validate_canonical
        result = validate_canonical(df_canonical, "NJ")
        print(f"Validator: Passed={result.passed}, Errors={len(result.errors)}, Warnings={len(result.warnings)}")

        tests_passed += 1
    except Exception as e:
        print(f"Component test failed: {e}")
        tests_failed += 1

    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Passed: {tests_passed}")
    print(f"Failed: {tests_failed}")
    print(f"{'='*60}\n")

    # Run golden file tests
    print(f"\n{'='*60}")
    print("TEST: Golden File Regression Tests")
    print(f"{'='*60}")
    print("Running golden file tests (format regression & determinism)...")
    print()

    golden_result = os.system("python tests/run_golden_tests.py")

    if golden_result != 0:
        tests_failed += 1
        print("\nGolden file tests failed!")
    else:
        tests_passed += 1

    print(f"\n{'='*60}")
    print("FINAL TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Passed: {tests_passed}")
    print(f"Failed: {tests_failed}")
    print(f"{'='*60}\n")

    if tests_failed > 0:
        print("Some tests failed. Check output above for details.")
        sys.exit(1)
    else:
        print("All tests passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()
