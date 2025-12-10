from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from api.v1.models.budget_rule import BudgetRule, BudgetPeriod
from api.v1.models.user import User
from api.v1.utils.logger import get_logger

logger = get_logger("budget_service")


class BudgetService:
    def __init__(self):
        pass

    def _calculate_next_reset_date(
        self, period: BudgetPeriod, current_date: datetime
    ) -> datetime:
        if period == BudgetPeriod.DAILY:
            return (current_date + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif period == BudgetPeriod.WEEKLY:
            days_until_monday = (7 - current_date.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            return (current_date + timedelta(days=days_until_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            next_month = current_date.replace(day=1) + timedelta(days=32)
            return next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def create_budget_rule(
        self,
        user_id: str,
        limit_amount: Decimal,
        period: BudgetPeriod,
        db: Session,
    ) -> BudgetRule:
        current_date = datetime.now(timezone.utc)
        next_reset_date = self._calculate_next_reset_date(period, current_date)

        budget_rule = BudgetRule(
            user_id=user_id,
            limit_amount=limit_amount,
            period=period,
            next_reset_date=next_reset_date,
        )

        db.add(budget_rule)
        db.commit()
        db.refresh(budget_rule)

        logger.info(
            "Budget rule created",
            extra={
                "budget_rule_id": budget_rule.id,
                "user_id": user_id,
                "limit_amount": str(limit_amount),
                "period": period.value,
            },
        )

        return budget_rule

    def get_user_budget_rules(self, user_id: str, db: Session) -> list[BudgetRule]:
        return list(
            db.scalars(select(BudgetRule).where(BudgetRule.user_id == user_id)).all()
        )

    def update_budget_rule(
        self,
        budget_rule_id: str,
        limit_amount: Optional[Decimal] = None,
        period: Optional[BudgetPeriod] = None,
        db: Session = None,
    ) -> Optional[BudgetRule]:
        budget_rule = db.scalar(
            select(BudgetRule).where(BudgetRule.id == budget_rule_id)
        )

        if not budget_rule:
            return None

        if limit_amount is not None:
            budget_rule.limit_amount = limit_amount
        if period is not None:
            budget_rule.period = period
            budget_rule.next_reset_date = self._calculate_next_reset_date(
                period, datetime.now(timezone.utc)
            )

        db.commit()
        db.refresh(budget_rule)

        return budget_rule


budget_service = BudgetService()
