from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from sports_passport.db.database import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # server_default mirrors migration e2f5b8c3d4a1 — see SyncState.enabled.
    used: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
