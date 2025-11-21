from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/validation", tags=["validation"])

class ValidationResponse(BaseModel):
    success: bool
    run_id: str = None
    message: str = None
    error: str = None

class ValidationErrorDetail(BaseModel):
    code: str
    field: str
    row: int
    message: str

class UploadResultResponse(BaseModel):
    success: bool
    run_id: str = None
    status: str = None
    message: str = None
    error: str = None
    error_count: int = 0
    warning_count: int = 0
    total_records: int = 0
    errors: list[ValidationErrorDetail] = []
    warnings: list[ValidationErrorDetail] = []

@router.post("/upload", response_model=UploadResultResponse)
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and validate a compliance document"""
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

        # Determine state code from tenant (default to NJ for MVP)
        state_code = "NJ"

        # Use tenant name for config lookup (not ID)
        artifact = adapter.generate(
            tenant_id=tenant.name.lower().replace(" ", "_"),
            state_code=state_code,
            source_file=str(temp_file_path),
            run_id=run.id
        )

        # Update run status based on validation results
        if artifact.validation and not artifact.validation.passed:
            run.status = "errors"
            error_count = len(artifact.validation.errors)
            warning_count = len(artifact.validation.warnings)
        elif artifact.validation:
            run.status = "completed"
            error_count = len(artifact.validation.errors)
            warning_count = len(artifact.validation.warnings)
        else:
            run.status = "completed"
            error_count = 0
            warning_count = 0

        # Save submission file path and other metadata
        if artifact.submission_file_path:
            run.submission_file_path = str(artifact.submission_file_path)

        if artifact.control_totals:
            run.record_count = artifact.control_totals.row_count

        # Store the full artifact manifest for later reference
        run.manifest = str(artifact.manifest) if artifact.manifest else None

        db.commit()

        # Prepare response
        errors_list = []
        warnings_list = []

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

            for warning in artifact.validation.warnings:
                row_val = warning.get("row", 0)
                # Convert row to int if it's a string
                if isinstance(row_val, str):
                    try:
                        row_val = int(row_val)
                    except (ValueError, TypeError):
                        row_val = 0

                warnings_list.append(ValidationErrorDetail(
                    code=warning.get("code", "UNKNOWN"),
                    field=warning.get("field", ""),
                    row=row_val,
                    message=warning.get("message", "")
                ))

        total_records = artifact.validation.row_count if artifact.validation else 0

        return UploadResultResponse(
            success=True,
            run_id=run.id,
            status=run.status,
            message=f"File {file.filename} processed successfully",
            error_count=error_count,
            warning_count=warning_count,
            total_records=total_records,
            errors=errors_list[:10],  # Limit to first 10 for response size
            warnings=warnings_list[:10]
        )

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

@router.get("/runs")
async def get_runs(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all validation runs for current user"""
    runs = db.query(ValidationRun).filter(ValidationRun.created_by_user_id == user_id).all()

    return {
        "success": True,
        "runs": [
            {
                "id": r.id,
                "filename": r.source_filename,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None
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

    tenant_name = tenant.name.lower().replace(" ", "_")
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

    tenant_name = tenant.name.lower().replace(" ", "_")
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

    tenant_name = tenant.name.lower().replace(" ", "_")
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

    tenant_name = tenant.name.lower().replace(" ", "_")
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

    tenant_name = tenant.name.lower().replace(" ", "_")
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
