import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from sports_passport.core.config import settings
from sports_passport.core.security import decode_access_token
from sports_passport.db.database import get_db
from sports_passport.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
_optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    email = payload.get("sub")
    if email is None:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    return user


def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensure the current user is an admin"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def require_metrics_access(
    token: str | None = Depends(_optional_oauth2_scheme),
    db: Session = Depends(get_db),
) -> None:
    """Gate /metrics: the Prometheus scrape token, or else an admin JWT.

    Prometheus can't hold a short-lived JWT, so it authenticates with the
    static METRICS_TOKEN. With no token configured, only admins get in.
    """
    if token and settings.metrics_token and secrets.compare_digest(
        token.encode(), settings.metrics_token.encode()
    ):
        return
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    get_current_admin_user(get_current_user(token=token, db=db))
