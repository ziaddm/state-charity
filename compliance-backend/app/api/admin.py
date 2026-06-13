from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone
from pathlib import Path
import yaml
import uuid
import logging

from app.database.connection import get_db
from app.database.models import User, Tenant
from app.services.tokens import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


def verify_admin(user_id: str, db: Session):
    """Helper function to verify user is admin"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


class TenantResponse(BaseModel):
    success: bool
    tenant_id: str = None
    message: str = None
    error: str = None


class TenantListResponse(BaseModel):
    success: bool
    tenants: list = []


@router.post("/tenants", response_model=TenantResponse)
async def create_tenant(
    tenant_name: str = Form(...),
    state_code: str = Form(...),
    config_file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new tenant with YAML configuration

    Requires:
    - tenant_name: Display name for the clinic/tenant
    - state_code: 2-letter state code (e.g., IL, NJ, CA)
    - config_file: YAML file with field mappings

    Admin only.
    """
    # Verify admin
    verify_admin(user_id, db)

    try:
        # Read and validate YAML
        yaml_content = await config_file.read()
        try:
            config = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML format: {str(e)}")

        # Validate required keys in YAML
        required_keys = ["field_mappings", "payer_source_mapping"]
        missing_keys = [k for k in required_keys if k not in config]
        if missing_keys:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid YAML structure. Missing keys: {', '.join(missing_keys)}"
            )

        # Validate field_mappings has required fields
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

        # Remove any special characters
        tenant_id = ''.join(c for c in tenant_id if c.isalnum() or c == '_')

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

        # Create tenant in database
        tenant = Tenant(
            id=tenant_id,
            name=tenant_name,
            state_code=state_code,
            created_at=datetime.now(timezone.utc)
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        # Save YAML configuration file
        config_dir = Path("compliance-backend/config/tenants")
        config_dir.mkdir(parents=True, exist_ok=True)

        yaml_path = config_dir / f"{tenant_id}.yaml"
        with open(yaml_path, "wb") as f:
            f.write(yaml_content)

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
    List all tenants in the system

    Admin only.
    """
    # Verify admin
    verify_admin(user_id, db)

    tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()

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
    Delete a tenant and its configuration

    WARNING: This will NOT delete associated data (users, patient_visits, runs).
    Only use this for cleaning up test tenants.

    Admin only.
    """
    # Verify admin
    verify_admin(user_id, db)

    # Get tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Check if tenant has users
    user_count = db.query(User).filter(User.tenant_id == tenant_id).count()
    if user_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete tenant. It has {user_count} associated user(s). Delete users first."
        )

    # Delete tenant from database
    db.delete(tenant)
    db.commit()

    # Delete YAML config file if it exists
    config_path = Path("compliance-backend/config/tenants") / f"{tenant_id}.yaml"
    if config_path.exists():
        config_path.unlink()

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
    Get the YAML configuration for a tenant

    Admin only.
    """
    # Verify admin
    verify_admin(user_id, db)

    # Verify tenant exists
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Read YAML config
    config_path = Path("compliance-backend/config/tenants") / f"{tenant_id}.yaml"
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="Configuration file not found")

    with open(config_path, "r") as f:
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
    List all users in the system with their tenant information

    Admin only.
    """
    # Verify admin
    verify_admin(user_id, db)

    # Get all users with tenant info
    users = db.query(User).order_by(User.created_at.desc()).all()

    # Get tenant mapping
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
