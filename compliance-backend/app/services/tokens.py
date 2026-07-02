from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
import os

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Cookie
from sqlalchemy.orm import Session

from app.database.connection import get_db  # also loads .env before os.getenv below
from app.database.models import RevokedToken, User

SECRET_KEY = os.getenv("SECRET_KEY")
_KNOWN_BAD_KEYS = {
    "change-me-before-production",
    "your-secret-key-change-in-production-12345",
}
if not SECRET_KEY or SECRET_KEY in _KNOWN_BAD_KEYS or len(SECRET_KEY) < 32:
    raise RuntimeError(
        "SECRET_KEY environment variable must be set to a random value of at least "
        "32 characters. Generate one with: "
        "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_jti(token: str) -> Optional[str]:
    """Decode a token without verifying expiry — used only during logout to extract JTI."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        return payload.get("jti")
    except JWTError:
        return None


def get_current_user(
    session: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> str:
    """
    FastAPI dependency: reads the HttpOnly session cookie, verifies the JWT,
    checks revocation, and confirms the account is still active and the token
    predates no password change. Returns the user_id string.
    """
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = jwt.decode(session, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        jti: Optional[str] = payload.get("jti")
        if not user_id or not jti:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    if db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been revoked")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is no longer valid")

    # Tokens issued before the last password change are invalid. Both sides are
    # floored to whole seconds because JWT iat has second resolution.
    changed_at = getattr(user, "password_changed_at", None)
    iat = payload.get("iat")
    if changed_at and iat is not None:
        if changed_at.tzinfo is None:
            changed_at = changed_at.replace(tzinfo=timezone.utc)
        issued = datetime.fromtimestamp(int(iat), tz=timezone.utc)
        if issued < changed_at.replace(microsecond=0):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is no longer valid")

    return user_id
