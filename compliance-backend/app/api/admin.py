from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone
import yaml
import logging

from app.database.connection import get_db
from app.database.models import User, Tenant, ValidationRun, PatientVisit
from app.paths import TENANT_CONFIG_DIR
from app.services.audit import record_event
from app.services.authz import is_platform_admin, require_admin, require_platform_admin
from app.services.tokens import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

MAX_CONFIG_BYTES = 1 * 1024 * 1024  # tenant YAML configs are small


class TenantResponse(BaseModel):
    success: bool
    tenant_id: str = None
    message: str = None
    error: str = None


class TenantListResponse(BaseModel):
    success: bool
    tenants: list = []


def _tenant_config_path(tenant_id: str):
    """Resolve a tenant's YAML path, refusing anything that escapes the config dir."""
    path = (TENANT_CONFIG_DIR / f"{tenant_id}.yaml").resolve()
    if path.parent != TENANT_CONFIG_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid tenant id")
    return path


@router.post("/tenants", response_model=TenantResponse)
async def create_tenant(
    tenant_name: str = Form(...),
    state_code: str = Form(...),
    config_file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new tenant with YAML configuration.

    Platform admin only.
    """
    admin = require_platform_admin(user_id, db)

    try:
        # Read and validate YAML
        yaml_content = await config_file.read(MAX_CONFIG_BYTES + 1)
        if len(yaml_content) > MAX_CONFIG_BYTES:
            raise HTTPException(status_code=413, detail="Configuration file too large (max 1 MB)")
        try:
            config = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML format: {str(e)}")

        if not isinstance(config, dict):
            raise HTTPException(status_code=400, detail="Invalid YAML structure: expected a mapping at the top level")

        # Validate required structure (must satisfy TenantMapper.validate_config)
        if "field_mappings" not in config:
            raise HTTPException(status_code=400, detail="Invalid YAML structure. Missing key: field_mappings")

        required_mapping_fields = [
            "patient_id", "last_name", "first_name", "date_of_birth",
            "visit_date", "payor_source"
        ]
        field_mappings = config.get("field_mappings", {})
        missing_mappings = [f for f in required_mapping_fields if f not in field_mappings]
        if missing_mappings:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required field mappings: {', '.join(missing_mappings)}"
            )

        # Generate tenant ID from name (lowercase, replace spaces with underscores)
        tenant_id = tenant_name.lower().replace(" ", "_").replace("-", "_")
        tenant_id = ''.join(c for c in tenant_id if c.isalnum() or c == '_').strip('_')
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant name must contain letters or digits")

        # Check for duplicate tenant ID
        existing = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Tenant with ID '{tenant_id}' already exists. Please use a different name."
            )

        # Validate state code (must be 2 letters)
        if len(state_code) != 2 or not state_code.isalpha():
            raise HTTPException(status_code=400, detail="State code must be 2 letters (e.g., IL, NJ)")

        state_code = state_code.upper()

        # The mapper loads configs by filename and requires a tenant_id key, so
        # keep both in sync with the generated id regardless of what the
        # uploaded file contained.
        config["tenant_id"] = tenant_id
        config.setdefault("tenant_name", tenant_name)

        # Save YAML configuration file first — a tenant row without its config
        # would be unusable.
        TENANT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        yaml_path = _tenant_config_path(tenant_id)
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True)

        # Create tenant in database. config_id ties the tenant to its YAML file
        # (upload processing refuses tenants without it).
        tenant = Tenant(
            id=tenant_id,
            name=tenant_name,
            state_code=state_code,
            config_id=tenant_id,
            created_at=datetime.now(timezone.utc)
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        record_event(db, "tenant_created", user_id=admin.id, tenant_id=tenant_id)
        logger.info(f"Created tenant: {tenant_id} ({tenant_name}) by admin {user_id}")

        return TenantResponse(
            success=True,
            tenant_id=tenant_id,
            message=f"Tenant '{tenant_name}' created successfully. You can now create users for this tenant."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating tenant: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create tenant: {str(e)}")


@router.get("/tenants", response_model=TenantListResponse)
async def list_tenants(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List tenants: platform admins see all, tenant admins see their own.
    """
    admin = require_admin(user_id, db)

    query = db.query(Tenant)
    if not is_platform_admin(admin):
        query = query.filter(Tenant.id == admin.tenant_id)
    tenants = query.order_by(Tenant.created_at.desc()).all()

    return TenantListResponse(
        success=True,
        tenants=[
            {
                "id": t.id,
                "name": t.name,
                "state_code": t.state_code,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in tenants
        ]
    )


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a tenant and its configuration.

    Platform admin only. Refuses if the tenant still has users, runs, or
    ingested patient data.
    """
    admin = require_platform_admin(user_id, db)

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    user_count = db.query(User).filter(User.tenant_id == tenant_id).count()
    if user_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete tenant. It has {user_count} associated user(s). Delete users first."
        )

    run_count = db.query(ValidationRun).filter(ValidationRun.tenant_id == tenant_id).count()
    visit_count = db.query(PatientVisit).filter(PatientVisit.tenant_id == tenant_id).count()
    if run_count > 0 or visit_count > 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot delete tenant. It has {run_count} run(s) and {visit_count} "
                "patient record(s). Remove its data first."
            )
        )

    db.delete(tenant)
    db.commit()

    # Delete YAML config file if it exists
    config_path = _tenant_config_path(tenant.config_id or tenant_id)
    if config_path.exists():
        config_path.unlink()

    record_event(db, "tenant_deleted", user_id=admin.id, tenant_id=tenant_id)
    logger.info(f"Deleted tenant: {tenant_id} by admin {user_id}")

    return {
        "success": True,
        "message": f"Tenant '{tenant.name}' deleted successfully"
    }


@router.get("/tenants/{tenant_id}/config")
async def get_tenant_config(
    tenant_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the YAML configuration for a tenant.

    Platform admins may read any tenant's config; tenant admins only their own.
    """
    admin = require_admin(user_id, db)
    if tenant_id != admin.tenant_id and not is_platform_admin(admin):
        raise HTTPException(status_code=403, detail="You can only view your own facility's configuration")

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    config_path = _tenant_config_path(tenant.config_id or tenant_id)
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="Configuration file not found")

    with open(config_path, "r", encoding="utf-8") as f:
        config_content = f.read()

    return {
        "success": True,
        "tenant_id": tenant_id,
        "tenant_name": tenant.name,
        "config": config_content
    }


@router.get("/users")
async def list_all_users(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List users: platform admins see everyone, tenant admins see their own tenant.
    """
    admin = require_admin(user_id, db)

    query = db.query(User)
    if not is_platform_admin(admin):
        query = query.filter(User.tenant_id == admin.tenant_id)
    users = query.order_by(User.created_at.desc()).all()

    tenant_map = {t.id: t.name for t in db.query(Tenant).all()}

    return {
        "success": True,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "role": u.role,
                "tenant_id": u.tenant_id,
                "tenant_name": tenant_map.get(u.tenant_id, "Unknown"),
                "is_active": u.is_active,
                "must_change_password": u.must_change_password,
                "last_login": u.last_login.isoformat() if u.last_login else None,
                "created_at": u.created_at.isoformat() if u.created_at else None
            }
            for u in users
        ]
    }
