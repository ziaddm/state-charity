from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone

from app.database.connection import get_db
from app.database.models import User
from app.services.password import hash_password, verify_password
from app.services.tokens import create_access_token, get_current_user
from app.services.email import send_temp_password_email

import secrets
import uuid

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    token: str = None
    user_id: str = None
    email: str = None
    role: str = None
    must_change_password: bool = False
    error: str = None

@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login endpoint - returns JWT token"""
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    
    # Create token
    token = create_access_token(user.id)
    
    return LoginResponse(
        success=True,
        token=token,
        user_id=user.id,
        email=user.email,
        role=user.role,
        must_change_password=user.must_change_password
    )

class CreateUserRequest(BaseModel):
    email: str
    role: str
    tenant_id: str

class CreateUserResponse(BaseModel):
    success: bool
    user_id: str = None
    email: str = None
    error: str = None

@router.post("/create-user", response_model=CreateUserResponse)
def create_user(
    request: CreateUserRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new User with temp password - admin only"""
    # Verify user is admin
    current_user = db.query(User).filter(User.id == user_id).first()
    if not current_user or current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")

    # check if user already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    temp_password = secrets.token_urlsafe(12)

    #Create user
    new_user = User(
        id = str(uuid.uuid4()),
        tenant_id = request.tenant_id,
        email = request.email,
        password_hash = hash_password(temp_password),
        role = request.role,
        is_active = True,
        must_change_password = True
    )

    # save to db
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # email
    send_temp_password_email(request.email, temp_password)

    return CreateUserResponse(success=True, user_id=new_user.id, email=new_user.email)

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class ChangePasswordResponse(BaseModel):
    success: bool
    message: str = None
    error: str = None

@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    request: ChangePasswordRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password - requires authentication via Bearer token"""
    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify old password
    if not verify_password(request.old_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Old password is incorrect")

    # Update password
    user.password_hash = hash_password(request.new_password)
    user.must_change_password = False  # User has now changed their password
    db.commit()

    return ChangePasswordResponse(
        success=True,
        message="Password changed successfully"
    )

class UserStatsResponse(BaseModel):
    total_users: int
    active_admins: int
    active_users: int

@router.get("/user-stats", response_model=UserStatsResponse)
def get_user_stats(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user statistics - admin only, scoped to their tenant"""
    # Verify user is admin
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")

    # Count users for this tenant only
    total_users = db.query(User).filter(
        User.tenant_id == user.tenant_id,
        User.is_active == True
    ).count()
    active_admins = db.query(User).filter(
        User.tenant_id == user.tenant_id,
        User.role == 'admin',
        User.is_active == True
    ).count()
    active_users = db.query(User).filter(
        User.tenant_id == user.tenant_id,
        User.role == 'user',
        User.is_active == True
    ).count()

    return UserStatsResponse(
        total_users=total_users,
        active_admins=active_admins,
        active_users=active_users
    )
