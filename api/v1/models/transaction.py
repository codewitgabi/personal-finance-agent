from __future__ import annotations

from typing import TYPE_CHECKING

from decimal import Decimal
from enum import Enum as PyEnum
from sqlalchemy import String, Numeric, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.v1.models.abstract_base import AbstractBaseModel

if TYPE_CHECKING:
    from api.v1.models.user import User


class TransactionType(PyEnum):
    CREDIT = "credit"
    DEBIT = "debit"


class TransactionSource(PyEnum):
    MANUAL = "manual"
    CSV_UPLOAD = "csv_upload"
    BANK_API = "bank_api"


class Transaction(AbstractBaseModel):
    __tablename__ = "transactions"

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, native_enum=False), nullable=False
    )
    source: Mapped[TransactionSource] = mapped_column(
        Enum(TransactionSource, native_enum=False), nullable=False
    )
    ai_category: Mapped[str] = mapped_column(String(100), nullable=True)
    ai_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="transactions")
