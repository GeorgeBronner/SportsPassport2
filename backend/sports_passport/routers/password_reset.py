import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

import mailtrap as mt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from sports_passport.core.config import settings
from sports_passport.core.limiter import limiter
from sports_passport.core.security import BCRYPT_MAX_PASSWORD_BYTES, get_password_hash
from sports_passport.db.database import get_db
from sports_passport.models.password_reset_token import PasswordResetToken
from sports_passport.models.user import User
from sports_passport.schemas.user import ForgotPasswordRequest, ResetPasswordRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _send_reset_email(to_email: str, to_name: str, reset_url: str) -> None:
    if not settings.mailtrap_api_key:
        logger.warning("MAILTRAP_API_KEY not set — skipping email send for %s. Link: %s", to_email, reset_url)
        return

    client = mt.MailtrapClient(token=settings.mailtrap_api_key)
    mail = mt.Mail(
        sender=mt.Address(email=settings.from_email, name=settings.from_name),
        to=[mt.Address(email=to_email, name=to_name)],
        subject="Reset your Sports Passport password",
        text=(
            f"Hi {to_name},\n\n"
            "We received a request to reset your Sports Passport password.\n\n"
            f"Click the link below to set a new password (valid for {settings.password_reset_token_expiry_minutes} minutes):\n\n"
            f"{reset_url}\n\n"
            "If you didn't request this, you can safely ignore this email.\n\n"
            "— The Sports Passport Team"
        ),
        html=(
            f"<p>Hi {to_name},</p>"
            "<p>We received a request to reset your Sports Passport password.</p>"
            f"<p><a href=\"{reset_url}\">Reset my password</a></p>"
            f"<p>This link is valid for {settings.password_reset_token_expiry_minutes} minutes. "
            "If you didn't request this, ignore this email.</p>"
            "<p>— The Sports Passport Team</p>"
        ),
        category="Password Reset",
    )
    client.send(mail)
    logger.info("Password reset email sent to %s", to_email)


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    # Always return success to avoid user enumeration
    user = db.query(User).filter(User.email == body.email).first()
    if user:
        # Invalidate any existing unused tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False,  # noqa: E712
        ).delete()

        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_token_expiry_minutes)

        db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))

        reset_url = f"{settings.app_base_url}/reset-password?token={raw_token}"
        try:
            _send_reset_email(to_email=user.email, to_name=user.full_name, reset_url=reset_url)
            db.commit()
            logger.info("Password reset requested for user_id=%s", user.id)
        except (mt.AuthorizationError, mt.APIError) as e:
            logger.error("Password reset email failed for user_id=%s: %s", user.id, e)
            db.rollback()

    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
def reset_password(request: Request, body: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = _hash_token(body.token)
    now = datetime.now(timezone.utc)

    reset_token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,  # noqa: E712
            PasswordResetToken.expires_at > now,
        )
        .first()
    )

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link.",
        )

    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Password must be at least 8 characters.",
        )
    if len(body.new_password.encode()) > BCRYPT_MAX_PASSWORD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes.",
        )

    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset link.",
        )

    user.password_hash = get_password_hash(body.new_password)
    reset_token.used = True
    db.commit()

    logger.info("Password reset completed for user_id=%s", user.id)
    return {"message": "Password updated successfully."}
