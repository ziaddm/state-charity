# Orchestrator file
# Will coordinate input, extraction, and mapping

# app/adapters/report_adapter.py
import uuid
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import pandas as pd

from app.extraction.extractor import load_source
from app.mapping.mapper import load_tenant_config
from app.models.artifacts import (
    ReportArtifact, ValidationResult, ControlTotals, compute_checksum
)
from app.writers.writer import write_fixed_width

logger = logging.getLogger(__name__)

class ReportAdapter:
    """
    Main adapter for generating state compliance reports.
    Implements Section 3.2 Adapter Pattern from spec.
    """
    
    def __init__(self, config_dir: str = "config", output_dir: str = "output"):
        self.config_dir = Path(config_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate(
        self,
        tenant_id: str,
        state_code: str,
        source_file: str,
        run_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> ReportArtifact:
        """
        Generate state report from tenant source data.
        
        Args:
            tenant_id: Tenant identifier (e.g., "acme_health")
            state_code: State code (e.g., "NJ", "NY")
            source_file: Path to tenant's input file
            run_id: Optional run identifier (auto-generated if not provided)
            params: Optional parameters for customization
        
        Returns:
            ReportArtifact with all outputs and metadata
        
        Raises:
            Exception: If any step fails (validation, transformation, etc.)
        """
        # Initialize run
        run_id = run_id or self._generate_run_id(tenant_id, state_code)
        start_time = time.time()
        params = params or {}
        
        logger.info(f"Starting report generation: run_id={run_id}, tenant={tenant_id}, state={state_code}")
        
        # Create tenant-scoped temp directory (Section 3.3)
        run_dir = self.output_dir / tenant_id / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        artifact = ReportArtifact(
            run_id=run_id,
            tenant_id=tenant_id,
            state_code=state_code,
            status="draft",
        )
        
        try:
            # Step 1: Load tenant source data
            logger.info(f"[{run_id}] Loading source file: {source_file}")
            df_raw, extract_meta = load_source(source_file)
            
            # Step 2: Load tenant mapping config
            logger.info(f"[{run_id}] Loading tenant mapping config")
            mapper = load_tenant_config(tenant_id, str(self.config_dir / "tenants"))

            # Step 3: PRE-VALIDATION - Check raw data structure
            logger.info(f"[{run_id}] Pre-validating raw data structure")
            artifact.status = "validating"

            from app.validation.pre_validator import validate_raw_structure

            pre_validation = validate_raw_structure(df_raw, mapper, state_code)

            # If pre-validation fails with errors, stop here
            if not pre_validation.passed:
                artifact.validation = pre_validation
                artifact.status = "errors"
                logger.error(f"[{run_id}] Pre-validation failed with {len(pre_validation.errors)} structural errors")

                # Build manifest for failed pre-validation
                artifact.manifest = {
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "tenant_name": mapper.tenant_name,
                    "state_code": state_code,
                    "source_file": str(source_file),
                    "status": "errors",
                    "validation_stage": "pre_validation",
                    "validation_failed": True,
                    "error_count": len(pre_validation.errors),
                    "warning_count": len(pre_validation.warnings),
                    "generation_timestamp": artifact.created_at,
                    "extract_metadata": extract_meta,
                    "mapping_summary": mapper.get_mapping_summary(),
                }

                elapsed = time.time() - start_time
                artifact.generation_time_seconds = elapsed
                bundle_paths = artifact.to_bundle(run_dir)
                logger.info(f"[{run_id}] Pre-validation artifacts written: {list(bundle_paths.keys())}")

                return artifact

            # Step 4: Map to canonical schema
            logger.info(f"[{run_id}] Mapping to canonical schema (pre-validation passed)")
            df_canonical, _ = mapper.map_dataframe(df_raw)  # Warnings already handled in pre-validation

            # Step 5: Apply coercions
            from app.validation.coercions import apply_coercions
            from app.schema.nj_schema import CANONICAL_VISITS_SCHEMA, CROSS_FIELD_RULES

            df_coerced = apply_coercions(df_canonical, CANONICAL_VISITS_SCHEMA)

            # Step 6: FIELD VALIDATION - Validate mapped field values
            logger.info(f"[{run_id}] Validating canonical field values")

            from app.validation.field_validator import validate_canonical_fields

            field_validation = validate_canonical_fields(
                df_coerced,
                CANONICAL_VISITS_SCHEMA,
                CROSS_FIELD_RULES,
                state_code
            )

            # Merge pre-validation warnings into field validation result
            field_validation.warnings.extend(pre_validation.warnings)
            field_validation.warning_count = len(field_validation.warnings)

            # Step 6.5: CONTROL TOTALS VALIDATION - Validate cross-record rules
            logger.info(f"[{run_id}] Validating control totals and cross-record rules")

            from app.validation.control_totals_validator import validate_control_totals

            # Compute control totals for validation
            temp_control_totals = self._compute_control_totals(df_coerced)

            control_validation = validate_control_totals(
                df_coerced,
                temp_control_totals,
                state_code
            )

            # Merge control validation into field validation
            field_validation.errors.extend(control_validation.errors)
            field_validation.warnings.extend(control_validation.warnings)
            field_validation.error_count = len(field_validation.errors)
            field_validation.warning_count = len(field_validation.warnings)
            field_validation.passed = len(field_validation.errors) == 0

            artifact.validation = field_validation

            # Step 7: Generate output file (even if validation failed - "fail open" philosophy)
            logger.info(f"[{run_id}] Generating {state_code} submission file")

            if not field_validation.passed:
                artifact.status = "errors"
                logger.warning(f"[{run_id}] Validation failed with {len(field_validation.errors)} errors, but continuing to process all records")
            else:
                artifact.status = "ready"

            output_filename = f"{tenant_id}_{state_code}_{datetime.now().strftime('%Y%m%d')}_{run_id[:8]}.txt"
            output_path = run_dir / output_filename

            # Write fixed-width format for state submission (process all records regardless of validation status)
            write_metadata = write_fixed_width(df_coerced, output_path, state_code)
            logger.info(f"[{run_id}] Fixed-width write: {write_metadata['records_written']} records, {write_metadata['bytes_written']} bytes")

            artifact.submission_file_path = output_path
            artifact.submission_file_checksum = compute_checksum(output_path)

            # Step 8: Calculate control totals
            logger.info(f"[{run_id}] Computing control totals")
            control_totals = self._compute_control_totals(df_coerced)
            artifact.control_totals = control_totals

            # Step 9: Build manifest with complete record count
            artifact.manifest = {
                "run_id": run_id,
                "tenant_id": tenant_id,
                "tenant_name": mapper.tenant_name,
                "state_code": state_code,
                "source_file": str(source_file),
                "submission_file": output_filename,
                "checksum_sha256": artifact.submission_file_checksum,
                "record_count": len(df_canonical),
                "records_written": write_metadata['records_written'],
                "validation_status": "errors" if not field_validation.passed else "passed",
                "error_count": len(field_validation.errors),
                "warning_count": len(field_validation.warnings),
                "generation_timestamp": artifact.created_at,
                "schema_version": "1.0.1",
                "extract_metadata": extract_meta,
                "mapping_summary": mapper.get_mapping_summary(),
            }

            # Complete
            elapsed = time.time() - start_time
            artifact.generation_time_seconds = elapsed

            logger.info(f"[{run_id}] Report generation complete in {elapsed:.2f}s (status: {artifact.status})")

            # Write artifact bundle
            bundle_paths = artifact.to_bundle(run_dir)
            logger.info(f"[{run_id}] Artifact bundle written: {list(bundle_paths.keys())}")

            return artifact
            
        except Exception as e:
            logger.error(f"[{run_id}] Report generation failed: {e}", exc_info=True)

            # Create error artifact instead of crashing
            artifact.status = "failed"

            # Determine appropriate error code based on exception type
            error_code = "E500"  # Default: schema_mismatch / processing error
            error_type = "processing_error"

            # Specific error codes for common failures
            if "KeyError" in str(type(e).__name__):
                error_code = "E500"
                error_type = "schema_mismatch"
            elif "FileNotFoundError" in str(type(e).__name__):
                error_code = "E501"
                error_type = "file_not_found"
            elif "PermissionError" in str(type(e).__name__):
                error_code = "E501"
                error_type = "permission_denied"

            # Add error details to validation result if it doesn't exist
            if not artifact.validation:
                artifact.validation = ValidationResult(
                    passed=False,
                    errors=[{
                        "code": error_code,
                        "severity": "error",
                        "type": error_type,
                        "field": "",
                        "message": f"Processing failed: {str(e)}",
                        "details": str(type(e).__name__)
                    }],
                    warnings=[],
                    row_count=0,
                    error_count=1,
                    warning_count=0
                )

            # Calculate elapsed time
            elapsed = time.time() - start_time
            artifact.generation_time_seconds = elapsed

            # Try to write what we have so user can see the error
            try:
                run_dir = self.output_dir / tenant_id / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                artifact.to_bundle(run_dir)
            except:
                pass  # If we can't write, just return the artifact

            return artifact
    
    def _generate_run_id(self, tenant_id: str, state_code: str) -> str:
        """Generate unique run identifier."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique = str(uuid.uuid4())[:8]
        return f"{tenant_id}_{state_code}_{timestamp}_{unique}"
    
    def _compute_control_totals(self, df: pd.DataFrame) -> ControlTotals:
        """Compute control totals per Section 5 spec."""
        return ControlTotals(
            row_count=len(df),
            sum_total_charges=df['total_charges'].astype(float).sum() if 'total_charges' in df else 0.0,
            sum_total_payment_received=df['total_payment_received'].astype(float).sum() if 'total_payment_received' in df else 0.0,
            by_payor_source=df['payor_source'].value_counts().to_dict() if 'payor_source' in df else {},
            by_claim_type=df['claim_type'].value_counts().to_dict() if 'claim_type' in df else {},
        )