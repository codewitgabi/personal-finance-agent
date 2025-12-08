from __future__ import annotations

from typing import TYPE_CHECKING

from decimal import Decimal
from sqlalchemy import String, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.v1.models.abstract_base import AbstractBaseModel

if TYPE_CHECKING:
    from api.v1.models.transaction import Transaction
    from api.v1.models.budget_rule import BudgetRule


class User(AbstractBaseModel):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    monthly_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=True)
    savings_goal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=True)

    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction", back_populates="user", cascade="all, delete-orphan"
    )
    budget_rules: Mapped[list[BudgetRule]] = relationship(
        "BudgetRule", back_populates="user", cascade="all, delete-orphan"
    )
