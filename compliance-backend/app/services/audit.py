"""
Minimal audit trail (spec §9: every action logged with tenant_id/run_id).

record_event never raises: an audit failure must not take down the request
that triggered it, but it is logged so operators can see the gap.
"""
import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.database.models import AuditLog

logger = logging.getLogger(__name__)


def record_event(
    db: Session,
    event_type: str,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> None:
    try:
        db.add(AuditLog(
            id=str(uuid.uuid4()),
            event_type=event_type,
            user_id=user_id,
            tenant_id=tenant_id,
            run_id=run_id,
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Audit write failed for event '{event_type}': {e}")
