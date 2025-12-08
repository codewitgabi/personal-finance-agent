from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from api.v1.models.abstract_base import AbstractBaseModel


class BlacklistedToken(AbstractBaseModel):
    __tablename__ = "blacklisted_tokens"

    token: Mapped[str] = mapped_column(
        String(500), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
