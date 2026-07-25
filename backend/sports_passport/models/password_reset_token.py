from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, false
from sqlalchemy.sql import func
from sports_passport.db.database import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    # server_default mirrors migration e2f5b8c3d4a1 — see SyncState.enabled.
    used = Column(Boolean, default=False, server_default=false(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_password_reset_tokens_token_hash", "token_hash"),
    )
