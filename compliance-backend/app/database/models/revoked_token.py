from sqlalchemy import Column, String, DateTime
from datetime import datetime, timezone
from .base import Base


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti = Column(String, primary_key=True)
    revoked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
