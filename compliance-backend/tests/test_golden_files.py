# tests/test_golden_files.py
"""
Golden File Tests - Regression Testing for State Submissions

Per MVP Spec Section 5.5:
- Golden-file tests for each state
- Ensures deterministic output (same input → same output)
- Catches unintended format changes before they reach production

Golden files are byte-for-byte references that validate:
- Fixed-width field positions remain correct
- Formatting logic doesn't change unexpectedly
- State submission format stays compliant
"""

import pytest
from pathlib import Path
import difflib
from app.adapters.report_adapter import ReportAdapter


class TestGoldenFiles:
    """Golden file regression tests for state submissions"""

    @pytest.fixture
    def adapter(self, golden_dir):
        """Create report adapter instance"""
        output_dir = golden_dir / "nj" / "test_output"
        return ReportAdapter(output_dir=str(output_dir))

    @pytest.fixture
    def golden_dir(self):
        """Golden files directory"""
        return Path(__file__).parent / "golden"

    def test_nj_golden_file(self, adapter, golden_dir):
        """
        Test NJ submission format matches golden reference file.

        This ensures:
        - Fixed-width format positions are correct (212 bytes per row)
        - Formatting logic hasn't changed
        - Output is deterministic (same input → same output)

        If this test fails:
        1. Review the diff to understand what changed
        2. If change is intentional (bug fix, format update):
           - Regenerate golden file: python -m app.main acme_health NJ tests/golden/nj/nj_submission_input.csv
           - Copy new output to tests/golden/nj/nj_submission.golden.txt
        3. If change is unintentional: you found a regression!
        """
        # Golden file paths
        input_file = golden_dir / "nj" / "nj_submission_input.csv"
        golden_file = golden_dir / "nj" / "nj_submission.golden.txt"

        # Ensure files exist
        assert input_file.exists(), f"Golden input file not found: {input_file}"
        assert golden_file.exists(), f"Golden reference file not found: {golden_file}"

        # Generate report using golden input
        artifact = adapter.generate(
            tenant_id="acme_health",
            state_code="NJ",
            source_file=str(input_file)
        )

        # Ensure generation succeeded
        assert artifact.status == "ready", f"Report generation failed: {artifact.status}"
        assert artifact.submission_file_path.exists(), "Submission file not generated"

        # Read actual output
        with open(artifact.submission_file_path, 'rb') as f:
            actual_bytes = f.read()

        # Read golden reference
        with open(golden_file, 'rb') as f:
            golden_bytes = f.read()

        # Compare byte-for-byte
        if actual_bytes != golden_bytes:
            # Generate human-readable diff for debugging
            actual_text = actual_bytes.decode('utf-8', errors='replace')
            golden_text = golden_bytes.decode('utf-8', errors='replace')

            diff = list(difflib.unified_diff(
                golden_text.splitlines(keepends=True),
                actual_text.splitlines(keepends=True),
                fromfile='golden_reference',
                tofile='actual_output',
                lineterm=''
            ))

            # Show detailed error
            error_msg = [
                "\n" + "=" * 80,
                "NJ SUBMISSION FORMAT CHANGED - REGRESSION DETECTED!",
                "=" * 80,
                f"Golden file: {golden_file}",
                f"Actual file: {artifact.submission_file_path}",
                f"Byte count: Golden={len(golden_bytes)}, Actual={len(actual_bytes)}",
                "",
                "DIFF (first 50 lines):",
                "=" * 80,
            ]
            error_msg.extend(diff[:50])

            if len(diff) > 50:
                error_msg.append(f"\n... ({len(diff) - 50} more lines)")

            error_msg.extend([
                "",
                "=" * 80,
                "TO FIX:",
                "1. Review diff above to understand what changed",
                "2. If change is intentional, update golden file:",
                f"   cp {artifact.submission_file_path} {golden_file}",
                "3. If change is unintentional, fix the regression!",
                "=" * 80,
            ])

            pytest.fail("\n".join(error_msg))

        # Test passed - output matches golden file exactly
        print(f"✓ NJ format matches golden reference ({len(actual_bytes)} bytes)")


    def test_nj_golden_file_determinism(self, adapter, golden_dir):
        """
        Test that running twice produces identical output (determinism).

        Per MVP Spec Section 3.1:
        "Determinism and auditability: the same input must always yield
        the same output, with full traceability of how the file was produced."
        """
        input_file = golden_dir / "nj" / "nj_submission_input.csv"

        # Create two separate adapters with different output dirs for determinism test
        adapter1 = ReportAdapter(output_dir=str(golden_dir / "nj" / "determinism_test_1"))
        adapter2 = ReportAdapter(output_dir=str(golden_dir / "nj" / "determinism_test_2"))

        # Generate report twice
        artifact1 = adapter1.generate(
            tenant_id="acme_health",
            state_code="NJ",
            source_file=str(input_file)
        )

        artifact2 = adapter2.generate(
            tenant_id="acme_health",
            state_code="NJ",
            source_file=str(input_file)
        )

        # Read both outputs
        with open(artifact1.submission_file_path, 'rb') as f:
            output1 = f.read()

        with open(artifact2.submission_file_path, 'rb') as f:
            output2 = f.read()

        # Compare - should be IDENTICAL
        assert output1 == output2, (
            f"Outputs differ! System is not deterministic.\n"
            f"Run 1: {len(output1)} bytes\n"
            f"Run 2: {len(output2)} bytes\n"
            f"This violates MVP Spec Section 3.1"
        )

        print(f"✓ Determinism verified - two runs produced identical output ({len(output1)} bytes)")


# Pytest configuration
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
