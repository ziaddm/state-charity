# main.py
"""
Compliance Reporting CLI - Entry Point
======================================

This is the command-line interface for the compliance analytics system.
It orchestrates the entire pipeline from file upload to state-ready submission.

Purpose:
    - Provide a simple CLI for operators to generate state compliance reports
    - Accept tenant data files (CSV/Excel) and convert to state submission format
    - Return validation results and submission artifacts

Usage:
    python -m app.main <tenant_id> <state_code> <source_file> [options]

Example:
    python -m app.main acme_health NJ test_data/acme_health_sample.csv

Exit Codes:
    0 = Success (file generated, no errors)
    1 = Failure (system error, file not found, configuration missing)
    2 = Validation errors (data issues that block submission)
"""
import sys
import logging
from pathlib import Path
import argparse

# Import the ReportAdapter - this is the orchestrator that runs the entire pipeline
from app.adapters.report_adapter import ReportAdapter

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
# Set up logging to both file and console
# - File log: compliance_reports.log (persistent audit trail)
# - Console: stdout (real-time feedback to operator)
# - Format includes timestamp, module name, severity, and message
logging.basicConfig(
    level=logging.INFO,  # Log INFO and above (INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('compliance_reports.log'),  # Persistent log file
        logging.StreamHandler(sys.stdout)              # Print to console
    ]
)

# Create logger for this module
logger = logging.getLogger(__name__)


# ============================================================================
# MAIN FUNCTION - CLI Entry Point
# ============================================================================
def main():
    """
    Main CLI function that handles command-line arguments and orchestrates report generation.

    This function:
    1. Parses command-line arguments (tenant_id, state, file path, etc.)
    2. Validates inputs (file exists, required args provided)
    3. Calls ReportAdapter to run the 8-step pipeline
    4. Prints summary to console
    5. Exits with appropriate code for CI/CD systems

    Command-line arguments are defined below using argparse.
    """

    # ========================================================================
    # ARGUMENT PARSING
    # ========================================================================
    # Set up argparse to handle command-line arguments
    parser = argparse.ArgumentParser(
        description="Generate state compliance reports from tenant data"
    )

    # REQUIRED ARGUMENTS (positional)
    # These must be provided in order: tenant_id, state_code, source_file

    parser.add_argument(
        "tenant_id",
        help="Tenant identifier (e.g., acme_health) - used to load config/tenants/{tenant_id}.yaml"
    )
    parser.add_argument(
        "state_code",
        help="State code (e.g., NJ, NY) - determines which schema to use"
    )
    parser.add_argument(
        "source_file",
        help="Path to tenant's input CSV/Excel file with patient visit data"
    )

    # OPTIONAL ARGUMENTS (flags with --)

    parser.add_argument(
        "--run-id",
        help="Optional run identifier (auto-generated timestamp-based ID if not provided). Used for tracking and audit trails."
    )
    parser.add_argument(
        "--config-dir",
        default="config",
        help="Configuration directory containing tenant YAML files (default: config)"
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory for submission files and artifacts (default: output)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",  # This makes it a boolean flag (present = True, absent = False)
        help="Validate only, don't write output files. Useful for testing validation without generating files."
    )

    # Parse the arguments from command line
    args = parser.parse_args()

    # ========================================================================
    # INPUT VALIDATION
    # ========================================================================
    # Before starting the pipeline, verify the source file exists
    # Exit early with error code 1 if file not found (saves time vs failing later)
    if not Path(args.source_file).exists():
        logger.error(f"Source file not found: {args.source_file}")
        sys.exit(1)  # Exit code 1 = system error (file not found)
    
    # ========================================================================
    # PIPELINE EXECUTION
    # ========================================================================
    try:
        # STEP 1: Initialize the ReportAdapter
        # --------------------------------------------------------------------
        # The adapter is the orchestrator that manages the entire 8-step pipeline:
        #   1. Extract data from file
        #   2. Pre-validate raw structure
        #   3. Map fields using tenant config
        #   4. Apply coercions (normalize data types)
        #   5. Validate canonical fields
        #   6. Validate control totals
        #   7. Write fixed-width output
        #   8. Bundle artifacts (manifest, validation, control totals)
        adapter = ReportAdapter(
            config_dir=args.config_dir,    # Where to find tenant YAML configs
            output_dir=args.output_dir     # Where to write output files
        )

        # STEP 2: Generate the report
        # --------------------------------------------------------------------
        # This is the main pipeline execution - all 8 steps happen inside this call
        logger.info(f"Generating {args.state_code} report for {args.tenant_id}")

        artifact = adapter.generate(
            tenant_id=args.tenant_id,      # Which tenant's config to use
            state_code=args.state_code,    # Which state schema to use (NJ, NY, etc.)
            source_file=args.source_file,  # Input file path
            run_id=args.run_id,            # Optional run ID (auto-generated if None)
            params={"dry_run": args.dry_run}  # Extra params like dry-run mode
        )

        # STEP 3: Print human-readable summary to console
        # --------------------------------------------------------------------
        # The artifact contains all results: validation, control totals, file paths, etc.
        # Print key information for operator review
        print("\n" + "="*60)
        print("REPORT GENERATION SUMMARY")
        print("="*60)
        print(f"Run ID:           {artifact.run_id}")         # Unique identifier for this run
        print(f"Tenant:           {artifact.tenant_id}")      # Which clinic's data
        print(f"State:            {artifact.state_code}")     # Which state format
        print(f"Status:           {artifact.status}")         # ready, errors, or failed

        # Show record count from control totals (if available)
        print(f"Records:          {artifact.control_totals.row_count if artifact.control_totals else 0}")

        # Show validation results (if validation ran)
        if artifact.validation:
            print(f"Validation:       {'PASSED' if artifact.validation.passed else 'FAILED'}")
            print(f"Errors:           {len(artifact.validation.errors)}")    # E-codes (block submission)
            print(f"Warnings:         {len(artifact.validation.warnings)}")  # W-codes (flag for review)

        # Show output file path and checksum (if file was written)
        if artifact.submission_file_path:
            print(f"Output File:      {artifact.submission_file_path}")
            print(f"Checksum:         {artifact.submission_file_checksum}")  # SHA256 for integrity verification

        # Show performance metric
        if artifact.generation_time_seconds:
            print(f"Generation Time:  {artifact.generation_time_seconds:.2f}s")

        print("="*60)

        # STEP 4: Exit with appropriate code
        # --------------------------------------------------------------------
        # Exit codes are important for CI/CD pipelines and automation
        # - 0 = Success (clean run, ready to submit)
        # - 1 = System failure (configuration missing, file format error, etc.)
        # - 2 = Validation errors (data problems that block submission)

        if artifact.status == "errors":
            # Validation found errors (E-codes) that block submission
            print("\nValidation errors detected. Review validation.json")
            sys.exit(2)  # Exit code 2 = validation errors
        elif artifact.status == "failed":
            # Pipeline failed (system error, not data validation issue)
            print("\nReport generation failed")
            sys.exit(1)  # Exit code 1 = system failure
        else:
            # Success! File generated and ready for submission
            print("\nReport generated successfully")
            sys.exit(0)  # Exit code 0 = success

    # ========================================================================
    # ERROR HANDLING
    # ========================================================================
    except FileNotFoundError as e:
        # Configuration file or required directory missing
        logger.error(f"Configuration error: {e}")
        sys.exit(1)  # Exit code 1 = configuration error

    except Exception as e:
        # Unexpected error (catch-all for anything else)
        # exc_info=True includes full stack trace in log file for debugging
        logger.error(f"Report generation failed: {e}", exc_info=True)
        sys.exit(1)  # Exit code 1 = unexpected failure


# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================
# This block only runs when the script is executed directly (not imported)
# Example: python -m app.main acme_health NJ data.csv
if __name__ == "__main__":
    main()