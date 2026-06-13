from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
import logging
import zipfile
import io

from app.database.connection import get_db
from app.database.models import ValidationRun, ValidationError, User, Tenant
from app.services.tokens import get_current_user
from app.adapters.report_adapter import ReportAdapter
from app.services.record_ingestion import ingest_records_from_artifact, calculate_file_hash

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/validation", tags=["validation"])

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

class ValidationResponse(BaseModel):
    success: bool
    run_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None

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
    total_records: int = 0

@router.post("/upload", response_model=UploadResultResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and validate a compliance document - returns immediately after validation"""
    temp_file_path = None
    try:
        # Get user and validate they exist
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get tenant info
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Create validation run record
        run = ValidationRun(
            id=str(uuid.uuid4()),
            tenant_id=user.tenant_id,
            created_by_user_id=user_id,
            source_filename=file.filename,
            status="processing",
            started_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc)
        )

        db.add(run)
        db.commit()
        db.refresh(run)

        # Save uploaded file to temp location
        temp_dir = tempfile.mkdtemp()
        temp_file_path = Path(temp_dir) / file.filename

        with open(temp_file_path, 'wb') as f:
            contents = await file.read()
            f.write(contents)

        # Process file using ReportAdapter
        logger.info(f"Processing file: {file.filename} for run {run.id}")

        adapter = ReportAdapter(config_dir="config", output_dir="output")

        # Resolve config_id (YAML filename key) from the tenant record
        state_code = tenant.state_code or "NJ"
        config_id = tenant.config_id
        if not config_id:
            raise HTTPException(
                status_code=500,
                detail=f"Tenant '{tenant.name}' has no config_id set — cannot locate mapping config"
            )

        artifact = adapter.generate(
            tenant_id=config_id,
            state_code=state_code,
            source_file=str(temp_file_path),
            run_id=run.id
        )

        # Update run status based on validation results - FAIL CLOSED
        # ANY errors = complete failure, no partial success
        if artifact.validation:
            error_count = len(artifact.validation.errors)
            logger.info(f"[RUN {run.id}] Validation completed with {error_count} errors")
            if error_count > 0:
                run.status = "errors"
                logger.error(f"[RUN {run.id}] Setting status to 'errors' - validation failed")
                # Log first few errors for debugging
                for i, err in enumerate(artifact.validation.errors[:3]):
                    logger.error(f"[RUN {run.id}]   Error {i+1}: [{err.get('code', 'NOCODE')}] {err.get('field', 'NOFIELD')} - {err.get('message', 'NO_MSG')[:100]}")
            else:
                run.status = "completed"
                logger.info(f"[RUN {run.id}] Validation passed - 0 errors")
        else:
            run.status = "completed"
            error_count = 0
            logger.warning(f"[RUN {run.id}] No validation object - assuming pass (THIS SHOULD NOT HAPPEN)")

        # Save submission file path and other metadata
        if artifact.submission_file_path:
            run.submission_file_path = str(artifact.submission_file_path)

        if artifact.control_totals:
            run.record_count = artifact.control_totals.row_count

        # Store the full artifact manifest for later reference
        run.manifest = str(artifact.manifest) if artifact.manifest else None

        db.commit()

        # FAIL CLOSED: Queue ingestion ONLY if validation passed with ZERO errors
        if error_count == 0:
            # Perfect validation - set initial ingestion status
            run.ingestion_status = "pending"
            run.status = "ready"  # Validation complete, files ready for download
            db.commit()

            # Queue background ingestion
            file_hash = calculate_file_hash(contents)
            logger.info(f"[RUN {run.id}] ✓ Validation passed (0 errors) - queuing background ingestion")
            background_tasks.add_task(
                background_ingest_task,
                run.id,
                artifact,
                user.tenant_id,
                file_hash,
                str(temp_file_path)
            )
        else:
            # FAIL CLOSED: ANY errors = complete rejection, no ingestion, no files
            run.ingestion_status = None
            run.status = "errors"
            logger.info(f"[RUN {run.id}] ✗ Validation FAILED: {error_count} errors found - BLOCKING upload and ingestion")

        # Prepare response - collect ALL errors from validation
        errors_list = []

        if artifact.validation:
            for error in artifact.validation.errors:
                row_val = error.get("row", 0)
                # Convert row to int if it's a string
                if isinstance(row_val, str):
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

        total_records = artifact.validation.row_count if artifact.validation else 0

        response = UploadResultResponse(
            success=True,
            run_id=run.id,
            status=run.status,
            ingestion_status=run.ingestion_status,
            message=f"File {file.filename} validated - {error_count} errors found" if error_count > 0 else f"File {file.filename} validated successfully - ingestion queued",
            error_count=error_count,
            total_records=total_records,
            records_ingested=0,  # Will be updated by background task
            errors=errors_list  # Return ALL errors, not just first 10
        )

        logger.info(f"[RUN {run.id}] Returning response: status={response.status}, error_count={response.error_count}, ingestion_status={response.ingestion_status}")
        return response

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        return UploadResultResponse(
            success=False,
            error=str(e)
        )

    finally:
        # Clean up temp files
        if temp_file_path and Path(temp_file_path).exists():
            try:
                shutil.rmtree(Path(temp_file_path).parent)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file: {e}")

@router.get("/status/{run_id}", response_model=RunStatusResponse)
async def get_run_status(
    run_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Poll status of a validation run (for real-time updates)"""
    run = db.query(ValidationRun).filter(
        ValidationRun.id == run_id,
        ValidationRun.created_by_user_id == user_id
    ).first()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

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
    """Get all validation runs for current user, newest first"""
    runs = (
        db.query(ValidationRun)
        .filter(ValidationRun.created_by_user_id == user_id)
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

@router.get("/tenants")
async def get_tenants(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all available tenants for admin user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Only admins can see all tenants
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can view tenants")

    tenants = db.query(Tenant).all()

    return {
        "success": True,
        "tenants": [
            {
                "id": t.id,
                "name": t.name
            }
            for t in tenants
        ]
    }

def get_current_user_optional(request: HTTPException = None, token: str = None, db: Session = Depends(get_db)):
    """Get current user from either Authorization header or token query param"""
    auth_header = request.headers.get("Authorization") if request else None
    token_to_use = None

    if auth_header and auth_header.startswith("Bearer "):
        token_to_use = auth_header[7:]
    elif token:
        token_to_use = token

    if not token_to_use:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication")

    from app.services.tokens import verify_token
    user_id = verify_token(token_to_use)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user_id

@router.get("/download/{run_id}")
async def download_result(
    run_id: str,
    token: str = None,
    request = None,
    db: Session = Depends(get_db)
):
    """Download the submission file from a validation run"""
    # Get user from token (either in header or query param)
    from app.services.tokens import verify_token

    auth_header = request.headers.get("Authorization") if hasattr(request, 'headers') else None
    token_to_use = None

    if auth_header and auth_header.startswith("Bearer "):
        token_to_use = auth_header[7:]
    elif token:
        token_to_use = token

    if not token_to_use:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    user_id = verify_token(token_to_use)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get the validation run
    run = db.query(ValidationRun).filter(ValidationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")

    # Verify the user owns this run
    if run.created_by_user_id != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Check if submission file path exists
    if not run.submission_file_path:
        raise HTTPException(status_code=404, detail="Submission file not generated yet")

    file_path = Path(run.submission_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Return the file
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type='text/plain'
    )

@router.get("/download/{run_id}/validation")
async def download_validation_report(
    run_id: str,
    token: str = None,
    request = None,
    db: Session = Depends(get_db)
):
    """Download the validation report (JSON) from a validation run"""
    # Get user from token (either in header or query param)
    from app.services.tokens import verify_token

    auth_header = request.headers.get("Authorization") if hasattr(request, 'headers') else None
    token_to_use = None

    if auth_header and auth_header.startswith("Bearer "):
        token_to_use = auth_header[7:]
    elif token:
        token_to_use = token

    if not token_to_use:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    user_id = verify_token(token_to_use)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get the validation run
    run = db.query(ValidationRun).filter(ValidationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")

    # Verify the user owns this run
    if run.created_by_user_id != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # The ReportAdapter saves to: output/{tenant_name}/{run_id}/{run_id}_validation.json
    # We store tenant_id (UUID), so we need to look up tenant name
    tenant = db.query(Tenant).filter(Tenant.id == run.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant_name = tenant.config_id or tenant.name.lower().replace(" ", "_")
    run_dir = Path("output") / tenant_name / run_id

    # Try multiple possible file names
    validation_file = None
    for filename in [f"{run_id}_validation.json", "validation.json"]:
        candidate = run_dir / filename
        if candidate.exists():
            validation_file = candidate
            break

    if not validation_file:
        raise HTTPException(status_code=404, detail="Validation report not found")

    # Return the file
    return FileResponse(
        path=validation_file,
        filename=f"{run_id}_validation.json",
        media_type='application/json'
    )

@router.get("/download/{run_id}/control-totals")
async def download_control_totals(
    run_id: str,
    token: str = None,
    request = None,
    db: Session = Depends(get_db)
):
    """Download the control totals report (JSON) from a validation run"""
    from app.services.tokens import verify_token

    auth_header = request.headers.get("Authorization") if hasattr(request, 'headers') else None
    token_to_use = None

    if auth_header and auth_header.startswith("Bearer "):
        token_to_use = auth_header[7:]
    elif token:
        token_to_use = token

    if not token_to_use:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    user_id = verify_token(token_to_use)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    run = db.query(ValidationRun).filter(ValidationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")

    if run.created_by_user_id != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    tenant = db.query(Tenant).filter(Tenant.id == run.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant_name = tenant.config_id or tenant.name.lower().replace(" ", "_")
    run_dir = Path("output") / tenant_name / run_id
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
    token: str = None,
    request = None,
    db: Session = Depends(get_db)
):
    """Download the manifest report (JSON) from a validation run"""
    from app.services.tokens import verify_token

    auth_header = request.headers.get("Authorization") if hasattr(request, 'headers') else None
    token_to_use = None

    if auth_header and auth_header.startswith("Bearer "):
        token_to_use = auth_header[7:]
    elif token:
        token_to_use = token

    if not token_to_use:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    user_id = verify_token(token_to_use)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    run = db.query(ValidationRun).filter(ValidationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")

    if run.created_by_user_id != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    tenant = db.query(Tenant).filter(Tenant.id == run.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant_name = tenant.config_id or tenant.name.lower().replace(" ", "_")
    run_dir = Path("output") / tenant_name / run_id
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
    token: str = None,
    request = None,
    db: Session = Depends(get_db)
):
    """Download all report artifacts (validation, control-totals, manifest) as a zip file"""
    from app.services.tokens import verify_token

    auth_header = request.headers.get("Authorization") if hasattr(request, 'headers') else None
    token_to_use = None

    if auth_header and auth_header.startswith("Bearer "):
        token_to_use = auth_header[7:]
    elif token:
        token_to_use = token

    if not token_to_use:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    user_id = verify_token(token_to_use)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get the validation run
    run = db.query(ValidationRun).filter(ValidationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")

    # Verify the user owns this run
    if run.created_by_user_id != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Get tenant info
    tenant = db.query(Tenant).filter(Tenant.id == run.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant_name = tenant.config_id or tenant.name.lower().replace(" ", "_")
    run_dir = Path("output") / tenant_name / run_id

    # Collect all report artifacts
    artifacts_to_zip = []

    # Validation report
    validation_file = run_dir / f"{run_id}_validation.json"
    if validation_file.exists():
        artifacts_to_zip.append((validation_file, f"{run_id}_validation.json"))

    # Control totals
    control_totals_file = run_dir / f"{run_id}_control_totals.json"
    if control_totals_file.exists():
        artifacts_to_zip.append((control_totals_file, f"{run_id}_control_totals.json"))

    # Manifest
    manifest_file = run_dir / f"{run_id}_manifest.json"
    if manifest_file.exists():
        artifacts_to_zip.append((manifest_file, f"{run_id}_manifest.json"))

    if not artifacts_to_zip:
        raise HTTPException(status_code=404, detail="No report artifacts found")

    # Create zip file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path, arcname in artifacts_to_zip:
            zip_file.write(file_path, arcname=arcname)

    zip_buffer.seek(0)

    # Return zip file as streaming response
    return StreamingResponse(
        iter([zip_buffer.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={run_id}_report.zip"}
    )

@router.get("/artifacts/{run_id}")
async def list_artifacts(
    run_id: str,
    token: str = None,
    request = None,
    db: Session = Depends(get_db)
):
    """List all available artifacts for a validation run"""
    from app.services.tokens import verify_token

    auth_header = request.headers.get("Authorization") if hasattr(request, 'headers') else None
    token_to_use = None

    if auth_header and auth_header.startswith("Bearer "):
        token_to_use = auth_header[7:]
    elif token:
        token_to_use = token

    if not token_to_use:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    user_id = verify_token(token_to_use)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    run = db.query(ValidationRun).filter(ValidationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")

    if run.created_by_user_id != user_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    tenant = db.query(Tenant).filter(Tenant.id == run.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant_name = tenant.config_id or tenant.name.lower().replace(" ", "_")
    run_dir = Path("output") / tenant_name / run_id

    artifacts = {
        "run_id": run_id,
        "available_files": []
    }

    # Check for each artifact type
    artifact_types = {
        "submission": (run_dir / f"{run_id}.txt", "fixed-width submission file"),
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
