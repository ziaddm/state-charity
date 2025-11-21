# tests/run_golden_tests.py
"""
Golden File Test Runner - Standalone (no pytest required)

Runs golden file regression tests to ensure state submission formats
remain byte-for-byte identical to reference files.
"""

from pathlib import Path
import difflib
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.adapters.report_adapter import ReportAdapter


def test_nj_golden_file():
    """
    Test NJ submission format matches golden reference file.

    Returns: (passed, message)
    """
    print("\n" + "=" * 80)
    print("TEST: NJ Golden File - Format Regression Test")
    print("=" * 80)

    # Setup
    golden_dir = Path(__file__).parent / "golden"
    input_file = golden_dir / "nj" / "nj_submission_input.csv"
    golden_file = golden_dir / "nj" / "nj_submission.golden.txt"

    # Ensure files exist
    if not input_file.exists():
        return False, f"Golden input file not found: {input_file}"

    if not golden_file.exists():
        return False, f"Golden reference file not found: {golden_file}"

    print(f"Input:  {input_file}")
    print(f"Golden: {golden_file}")

    # Generate report
    print("\nGenerating report from golden input...")
    adapter = ReportAdapter(output_dir=str(golden_dir / "nj" / "test_output"))

    try:
        artifact = adapter.generate(
            tenant_id="acme_health",
            state_code="NJ",
            source_file=str(input_file)
        )
    except Exception as e:
        return False, f"Report generation failed: {e}"

    # Check generation succeeded
    if artifact.status != "ready":
        return False, f"Report generation failed: status={artifact.status}"

    if not artifact.submission_file_path.exists():
        return False, "Submission file not generated"

    print(f"Output: {artifact.submission_file_path}")

    # Read files
    with open(artifact.submission_file_path, 'rb') as f:
        actual_bytes = f.read()

    with open(golden_file, 'rb') as f:
        golden_bytes = f.read()

    print(f"\nByte counts: Golden={len(golden_bytes)}, Actual={len(actual_bytes)}")

    # Compare
    if actual_bytes == golden_bytes:
        print("\n[PASS] Output matches golden file exactly!")
        print(f"  Format is correct ({len(actual_bytes)} bytes)")
        return True, "NJ format matches golden reference"

    # Failed - show diff
    print("\n[FAIL] Output differs from golden file!")
    print("\n" + "=" * 80)
    print("REGRESSION DETECTED - Format Changed")
    print("=" * 80)

    # Generate diff
    actual_text = actual_bytes.decode('utf-8', errors='replace')
    golden_text = golden_bytes.decode('utf-8', errors='replace')

    diff = list(difflib.unified_diff(
        golden_text.splitlines(keepends=True),
        actual_text.splitlines(keepends=True),
        fromfile='golden_reference',
        tofile='actual_output',
        lineterm=''
    ))

    print("\nDIFF (first 30 lines):")
    for i, line in enumerate(diff[:30]):
        print(line.rstrip())

    if len(diff) > 30:
        print(f"\n... ({len(diff) - 30} more diff lines)")

    print("\n" + "=" * 80)
    print("TO FIX:")
    print("1. Review diff above to understand what changed")
    print("2. If change is intentional, update golden file:")
    print(f"   cp {artifact.submission_file_path} {golden_file}")
    print("3. If change is unintentional, fix the regression!")
    print("=" * 80)

    return False, "Output differs from golden file"


def test_nj_determinism():
    """
    Test that running twice produces identical output (determinism).

    Returns: (passed, message)
    """
    print("\n" + "=" * 80)
    print("TEST: NJ Determinism - Same Input -> Same Output")
    print("=" * 80)

    golden_dir = Path(__file__).parent / "golden"
    input_file = golden_dir / "nj" / "nj_submission_input.csv"

    print(f"Input: {input_file}")
    print("\nGenerating report twice...")

    # Generate report twice
    try:
        adapter1 = ReportAdapter(output_dir=str(golden_dir / "nj" / "determinism_test_1"))
        artifact1 = adapter1.generate(
            tenant_id="acme_health",
            state_code="NJ",
            source_file=str(input_file)
        )

        adapter2 = ReportAdapter(output_dir=str(golden_dir / "nj" / "determinism_test_2"))
        artifact2 = adapter2.generate(
            tenant_id="acme_health",
            state_code="NJ",
            source_file=str(input_file)
        )
    except Exception as e:
        return False, f"Report generation failed: {e}"

    # Read both outputs
    with open(artifact1.submission_file_path, 'rb') as f:
        output1 = f.read()

    with open(artifact2.submission_file_path, 'rb') as f:
        output2 = f.read()

    print(f"Run 1: {len(output1)} bytes")
    print(f"Run 2: {len(output2)} bytes")

    # Compare
    if output1 == output2:
        print("\n[PASS] Two runs produced identical output!")
        print(f"  System is deterministic ({len(output1)} bytes)")
        return True, "Determinism verified"

    print("\n[FAIL] Outputs differ!")
    print("System is NOT deterministic (violates MVP Spec Section 3.1)")
    return False, f"Outputs differ: {len(output1)} vs {len(output2)} bytes"


def main():
    """Run all golden file tests"""
    print("\n" + "=" * 80)
    print("GOLDEN FILE REGRESSION TESTS")
    print("=" * 80)
    print("\nPer MVP Spec Section 5.5: Golden-file tests for each state")
    print("Ensures deterministic output and catches format regressions")

    tests = [
        ("NJ Golden File Match", test_nj_golden_file),
        ("NJ Determinism", test_nj_determinism),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            passed, message = test_func()
            results.append((test_name, passed, message))
        except Exception as e:
            # Convert exception to plain string to avoid unicode issues
            error_msg = str(e).encode('ascii', errors='replace').decode('ascii')
            results.append((test_name, False, f"Exception: {error_msg}"))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed_count = sum(1 for _, passed, _ in results if passed)
    total_count = len(results)

    for test_name, passed, message in results:
        status = "PASSED" if passed else "FAILED"
        symbol = "[PASS]" if passed else "[FAIL]"
        print(f"{symbol} {test_name}: {status}")
        if not passed:
            print(f"  -> {message}")

    print(f"\nTotal: {passed_count}/{total_count} passed")
    print("=" * 80)

    # Exit code
    if passed_count == total_count:
        print("\n[PASS] All golden file tests passed!")
        return 0
    else:
        print(f"\n[FAIL] {total_count - passed_count} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
