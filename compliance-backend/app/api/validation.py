from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Tuple
import os
import uuid
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
import logging
import zipfile
import io

from app.database.connection import get_db
from app.database.models import ValidationRun, User, Tenant
from app.paths import OUTPUT_DIR
from app.services.audit import record_event
from app.services.tokens import get_current_user
from app.adapters.report_adapter import ReportAdapter
from app.services.record_ingestion import ingest_records_from_artifact, calculate_file_hash

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/validation", tags=["validation"])

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024


# Background task for ingestion
def background_ingest_task(run_id: str, artifact: any, tenant_id: str, file_hash: str, source_file_path: str):
    """Background task to ingest records without blocking the response"""
    from app.database.connection import get_db

    db = next(get_db())
    try:
        # Update status to uploading
        run = db.query(ValidationRun).filter(ValidationRun.id == run_id).first()
        if run:
            run.ingestion_status = "in_progress"
            run.status = "uploading"
            db.commit()

        logger.info(f"[BACKGROUND] Starting ingestion for run {run_id}")

        records_ingested = ingest_records_from_artifact(
            db=db,
            artifact=artifact,
            tenant_id=tenant_id,
            run_id=run_id,
            file_hash=file_hash,
            source_file_path=source_file_path
        )

        # Update run with results
        run = db.query(ValidationRun).filter(ValidationRun.id == run_id).first()
        if run:
            run.records_ingested = records_ingested
            run.ingestion_status = "completed"
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()

        logger.info(f"[BACKGROUND] Completed ingestion for run {run_id}: {records_ingested} records")

    except Exception as e:
        logger.error(f"[BACKGROUND] Error during ingestion for run {run_id}: {e}", exc_info=True)
        # Update run with failure status
        run = db.query(ValidationRun).filter(ValidationRun.id == run_id).first()
        if run:
            run.ingestion_status = "failed"
            db.commit()
    finally:
        db.close()


class ValidationErrorDetail(BaseModel):
    code: str
    field: str
    row: int
    message: str


class UploadResultResponse(BaseModel):
    success: bool
    run_id: Optional[str] = None
    status: Optional[str] = None
    ingestion_status: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    error_count: int = 0
    total_records: int = 0
    records_ingested: int = 0
    errors: list[ValidationErrorDetail] = []


class RunStatusResponse(BaseModel):
    run_id: str
    status: str
    ingestion_status: Optional[str] = None
    records_ingested: int = 0
    error_count: int = 0
    warning_count: int = 0
    total_records: int = 0


def _get_run_for_user(run_id: str, user_id: str, db: Session) -> Tuple[ValidationRun, User]:
    """Load a run, authorizing by tenant: users may access any run belonging to
    their own facility (History is facility-wide)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    run = db.query(ValidationRun).filter(ValidationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")

    if run.tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    return run, user


def _run_output_dir(run: ValidationRun, db: Session) -> Path:
    """Resolve the artifact directory for a run: output/{config_id}/{run_id}."""
    tenant = db.query(Tenant).filter(Tenant.id == run.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant_name = tenant.config_id or tenant.name.lower().replace(" ", "_")
    return OUTPUT_DIR / tenant_name / run.id


@router.post("/upload", response_model=UploadResultResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and validate a compliance document - returns immediately after validation"""
    temp_dir = None
    try:
        # Get user and validate they exist
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get tenant info
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Validate file type before doing any work. The original filename is
        # kept only as display metadata — it never touches the filesystem.
        extension = Path(file.filename or "").suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{extension or 'none'}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        # Enforce the size cap while reading so oversized uploads cannot
        # exhaust memory (read one byte past the limit to detect overflow).
        contents = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit"
            )
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        # Resolve config_id (YAML filename key) from the tenant record
        state_code = tenant.state_code or "NJ"
        config_id = tenant.config_id
        if not config_id:
            raise HTTPException(
                status_code=500,
                detail=f"Tenant '{tenant.name}' has no config_id set — cannot locate mapping config"
            )

        # Create validation run record
        run = ValidationRun(
            id=str(uuid.uuid4()),
            tenant_id=user.tenant_id,
            created_by_user_id=user_id,
            state_code=state_code,
            source_filename=file.filename,
            source_file_hash=calculate_file_hash(contents),
            status="processing",
            started_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )

        db.add(run)
        db.commit()
        db.refresh(run)
        record_event(db, "file_uploaded", user_id=user_id, tenant_id=user.tenant_id, run_id=run.id)

        # Save uploaded file under a generated name (never the client filename)
        temp_dir = tempfile.mkdtemp()
        temp_file_path = Path(temp_dir) / f"upload_{uuid.uuid4().hex}{extension}"
        with open(temp_file_path, 'wb') as f:
            f.write(contents)

        # Process file using ReportAdapter (config/output resolved via app.paths)
        logger.info(f"Processing file: {file.filename} for run {run.id}")
        adapter = ReportAdapter()

        artifact = adapter.generate(
            tenant_id=config_id,
            state_code=state_code,
            source_file=str(temp_file_path),
            run_id=run.id
        )

        # Update run status based on validation results - FAIL CLOSED
        # ANY errors = complete failure, no partial success
        errors = artifact.validation.errors if artifact.validation else []
        error_count = len(errors)
        row_count = artifact.validation.row_count if artifact.validation else 0

        if artifact.validation is None:
            logger.warning(f"[RUN {run.id}] No validation object - assuming pass (THIS SHOULD NOT HAPPEN)")

        # Persist counters so History and status polling report real numbers.
        # valid_count: rows with no blocking issue. File-level errors (row not
        # a number) mean no row can be trusted.
        error_rows = {e.get("row") for e in errors if isinstance(e.get("row"), int)}
        has_file_level_error = any(not isinstance(e.get("row"), int) for e in errors)
        run.record_count = row_count
        run.error_count = error_count
        run.warning_count = artifact.validation.warning_count if artifact.validation else 0
        if error_count == 0:
            run.valid_count = row_count
        elif has_file_level_error:
            run.valid_count = 0
        else:
            run.valid_count = max(row_count - len(error_rows), 0)

        if artifact.submission_file_path:
            run.submission_file_path = str(artifact.submission_file_path)

        if error_count == 0:
            # Perfect validation - queue background ingestion
            run.ingestion_status = "pending"
            run.status = "ready"  # Validation complete, files ready for download
            db.commit()

            logger.info(f"[RUN {run.id}] Validation passed (0 blocking issues) - queuing background ingestion")
            background_tasks.add_task(
                background_ingest_task,
                run.id,
                artifact,
                user.tenant_id,
                run.source_file_hash,
                str(temp_file_path)
            )
        else:
            # FAIL CLOSED: ANY errors = complete rejection, no ingestion, no files
            run.ingestion_status = None
            run.status = "errors"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"[RUN {run.id}] Validation FAILED: {error_count} blocking issues - upload rejected")
            record_event(db, "validation_failed", user_id=user_id, tenant_id=user.tenant_id, run_id=run.id)

        # Prepare response - collect ALL blocking issues
        errors_list = []
        for error in errors:
            row_val = error.get("row", 0)
            if not isinstance(row_val, int):
                try:
                    row_val = int(row_val)
                except (ValueError, TypeError):
                    row_val = 0

            errors_list.append(ValidationErrorDetail(
                code=error.get("code", "UNKNOWN"),
                field=error.get("field", ""),
                row=row_val,
                message=error.get("message", "")
            ))

        response = UploadResultResponse(
            success=True,
            run_id=run.id,
            status=run.status,
            ingestion_status=run.ingestion_status,
            message=(
                f"File {file.filename} validated - {error_count} blocking issues found"
                if error_count > 0
                else f"File {file.filename} validated successfully - ingestion queued"
            ),
            error_count=error_count,
            total_records=row_count,
            records_ingested=0,  # Will be updated by background task
            errors=errors_list
        )

        logger.info(f"[RUN {run.id}] Returning response: status={response.status}, error_count={response.error_count}, ingestion_status={response.ingestion_status}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        return UploadResultResponse(
            success=False,
            error=str(e)
        )

    finally:
        # Clean up temp files
        if temp_dir and Path(temp_dir).exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file: {e}")


@router.get("/status/{run_id}", response_model=RunStatusResponse)
async def get_run_status(
    run_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Poll status of a validation run (for real-time updates)"""
    run, _ = _get_run_for_user(run_id, user_id, db)

    return RunStatusResponse(
        run_id=run.id,
        status=run.status or "processing",
        ingestion_status=run.ingestion_status,
        records_ingested=run.records_ingested or 0,
        error_count=run.error_count or 0,
        warning_count=run.warning_count or 0,
        total_records=run.record_count or 0
    )


@router.get("/runs")
async def get_runs(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all validation runs for the current user's facility, newest first"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    runs = (
        db.query(ValidationRun)
        .filter(ValidationRun.tenant_id == user.tenant_id)
        .order_by(ValidationRun.created_at.desc())
        .all()
    )

    return {
        "success": True,
        "runs": [
            {
                "id": r.id,
                "filename": r.source_filename,
                "status": r.status,
                "ingestion_status": r.ingestion_status,
                "records_ingested": r.records_ingested or 0,
                "error_count": r.error_count or 0,
                "warning_count": r.warning_count or 0,
                "record_count": r.record_count or 0,
                "valid_count": r.valid_count or 0,
                "has_submission_file": bool(r.submission_file_path and Path(r.submission_file_path).exists()),
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
        ]
    }


@router.get("/download/{run_id}")
async def download_result(
    run_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download the submission file from a validation run"""
    run, user = _get_run_for_user(run_id, user_id, db)

    if not run.submission_file_path:
        raise HTTPException(status_code=404, detail="Submission file not generated yet")

    file_path = Path(run.submission_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    record_event(db, "submission_downloaded", user_id=user_id, tenant_id=user.tenant_id, run_id=run_id)

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type='text/plain'
    )


@router.get("/download/{run_id}/validation")
async def download_validation_report(
    run_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download the validation report (JSON) from a validation run"""
    run, _ = _get_run_for_user(run_id, user_id, db)
    run_dir = _run_output_dir(run, db)

    validation_file = run_dir / f"{run_id}_validation.json"
    if not validation_file.exists():
        raise HTTPException(status_code=404, detail="Validation report not found")

    return FileResponse(
        path=validation_file,
        filename=f"{run_id}_validation.json",
        media_type='application/json'
    )


@router.get("/download/{run_id}/control-totals")
async def download_control_totals(
    run_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download the control totals report (JSON) from a validation run"""
    run, _ = _get_run_for_user(run_id, user_id, db)
    run_dir = _run_output_dir(run, db)

    control_totals_file = run_dir / f"{run_id}_control_totals.json"
    if not control_totals_file.exists():
        raise HTTPException(status_code=404, detail="Control totals report not found")

    return FileResponse(
        path=control_totals_file,
        filename=f"{run_id}_control_totals.json",
        media_type='application/json'
    )


@router.get("/download/{run_id}/manifest")
async def download_manifest(
    run_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download the manifest report (JSON) from a validation run"""
    run, _ = _get_run_for_user(run_id, user_id, db)
    run_dir = _run_output_dir(run, db)

    manifest_file = run_dir / f"{run_id}_manifest.json"
    if not manifest_file.exists():
        raise HTTPException(status_code=404, detail="Manifest report not found")

    return FileResponse(
        path=manifest_file,
        filename=f"{run_id}_manifest.json",
        media_type='application/json'
    )


@router.get("/download/{run_id}/report")
async def download_report_bundle(
    run_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download all report artifacts (validation, control-totals, manifest) as a zip file"""
    run, user = _get_run_for_user(run_id, user_id, db)
    run_dir = _run_output_dir(run, db)

    # Collect all report artifacts
    artifacts_to_zip = []
    for suffix in ("validation", "control_totals", "manifest"):
        candidate = run_dir / f"{run_id}_{suffix}.json"
        if candidate.exists():
            artifacts_to_zip.append((candidate, candidate.name))

    if not artifacts_to_zip:
        raise HTTPException(status_code=404, detail="No report artifacts found")

    # Create zip file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path, arcname in artifacts_to_zip:
            zip_file.write(file_path, arcname=arcname)

    zip_buffer.seek(0)
    record_event(db, "report_downloaded", user_id=user_id, tenant_id=user.tenant_id, run_id=run_id)

    return StreamingResponse(
        iter([zip_buffer.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={run_id}_report.zip"}
    )


@router.get("/artifacts/{run_id}")
async def list_artifacts(
    run_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all available artifacts for a validation run"""
    run, _ = _get_run_for_user(run_id, user_id, db)
    run_dir = _run_output_dir(run, db)

    artifacts = {
        "run_id": run_id,
        "available_files": []
    }

    # Check for each artifact type
    artifact_types = {
        "submission": (Path(run.submission_file_path) if run.submission_file_path else run_dir / f"{run_id}.txt", "fixed-width submission file"),
        "validation": (run_dir / f"{run_id}_validation.json", "validation results"),
        "control_totals": (run_dir / f"{run_id}_control_totals.json", "control totals"),
        "manifest": (run_dir / f"{run_id}_manifest.json", "processing manifest")
    }

    for artifact_key, (file_path, description) in artifact_types.items():
        if file_path.exists():
            artifacts["available_files"].append({
                "type": artifact_key,
                "filename": file_path.name,
                "description": description,
                "url": f"/api/validation/download/{run_id}/{artifact_key}" if artifact_key != "submission" else f"/api/validation/download/{run_id}"
            })

    return artifacts
