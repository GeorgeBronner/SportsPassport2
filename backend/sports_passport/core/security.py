from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sports_passport.core.config import settings

# bcrypt operates on at most the first 72 bytes of the password and raises a
# ValueError for anything longer, so truncate to match that limit explicitly.
BCRYPT_MAX_PASSWORD_BYTES = 72

MIN_PASSWORD_LENGTH = 8


def _encode_password(password: str) -> bytes:
    """Encode a password to the bytes bcrypt accepts (max 72 bytes)."""
    return password.encode("utf-8")[:BCRYPT_MAX_PASSWORD_BYTES]


def validate_password(password: str) -> None:
    """Enforce the same rules everywhere a password is set (register, change, reset).

    The upper bound matters as much as the lower one: bcrypt truncates past 72
    bytes, so without this check register would silently store the first 72
    bytes of a longer password while the reset flow rejects it outright.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters",
        )
    if len(password.encode()) > BCRYPT_MAX_PASSWORD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes",
        )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(_encode_password(plain_password), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return bcrypt.hashpw(_encode_password(password), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT access token"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None
