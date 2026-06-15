from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
import os

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Cookie
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import RevokedToken

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-before-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "exp": expire,
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
    and checks it has not been revoked. Returns the user_id string.
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

    return user_id
