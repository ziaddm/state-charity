from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from datetime import datetime, timezone
from .base import Base

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"))
    user_id = Column(String, ForeignKey("users.id"))
    run_id = Column(String, ForeignKey("runs.id"))
    event_type = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))