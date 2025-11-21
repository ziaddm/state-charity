from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from datetime import datetime
from .base import Base
from datetime import datetime, timezone

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String)
    is_active = Column(Boolean, default=False)
    must_change_password = Column(Boolean, default=True)
    last_login = Column(DateTime)
    created_by_user_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))