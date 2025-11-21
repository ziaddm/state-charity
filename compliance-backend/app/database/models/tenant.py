from sqlalchemy import Column, String, DateTime
from datetime import datetime
from .base import Base
from datetime import datetime, timezone

class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    state_code = Column(String(2))
    config_path = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))