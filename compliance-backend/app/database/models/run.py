from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from datetime import datetime
from .base import Base
from datetime import datetime, timezone

class ValidationRun(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    created_by_user_id = Column(String, ForeignKey("users.id"))
    state_code = Column(String(2))
    status = Column(String)  # "validating", "ready", "uploading", "completed", "errors"
    ingestion_status = Column(String)  # "pending", "in_progress", "completed", "failed"
    records_ingested = Column(Integer, default=0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    record_count = Column(Integer, default=0)
    valid_count = Column(Integer, default=0)
    source_filename = Column(String)
    source_file_hash = Column(String)
    submission_file_path = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))