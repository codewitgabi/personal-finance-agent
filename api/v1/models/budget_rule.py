from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from sqlalchemy import String, Numeric, ForeignKey, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.v1.models.abstract_base import AbstractBaseModel

if TYPE_CHECKING:
    from api.v1.models.user import User


class BudgetPeriod(PyEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class BudgetRule(AbstractBaseModel):
    __tablename__ = "budget_rules"

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    period: Mapped[BudgetPeriod] = mapped_column(
        Enum(BudgetPeriod, native_enum=False), nullable=False
    )
    next_reset_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    user: Mapped[User] = relationship("User", back_populates="budget_rules")
