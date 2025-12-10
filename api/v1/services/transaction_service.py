from decimal import Decimal
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from api.v1.models.transaction import Transaction, TransactionType, TransactionSource
from api.v1.models.user import User
from api.v1.utils.logger import get_logger

logger = get_logger("transaction_service")


class TransactionService:
    def __init__(self):
        pass

    def create_transaction(
        self,
        user_id: str,
        amount: Decimal,
        transaction_type: TransactionType,
        source: TransactionSource,
        ai_category: Optional[str] = None,
        ai_confidence: Optional[Decimal] = None,
        db: Session = None,
    ) -> Transaction:
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            type=transaction_type,
            source=source,
            ai_category=ai_category,
            ai_confidence=ai_confidence,
        )

        db.add(transaction)
        db.commit()
        db.refresh(transaction)

        logger.info(
            "Transaction created",
            extra={
                "transaction_id": transaction.id,
                "user_id": user_id,
                "amount": str(amount),
                "category": ai_category,
            },
        )

        return transaction

    def get_user_transactions(
        self, user_id: str, db: Session, limit: Optional[int] = None
    ) -> list[Transaction]:
        query = select(Transaction).where(Transaction.user_id == user_id).order_by(
            Transaction.created_at.desc()
        )
        if limit:
            query = query.limit(limit)

        return list(db.scalars(query).all())

    def get_transactions_by_category(
        self, user_id: str, category: str, db: Session
    ) -> list[Transaction]:
        return list(
            db.scalars(
                select(Transaction).where(
                    Transaction.user_id == user_id,
                    Transaction.ai_category == category,
                )
            ).all()
        )

    def get_spending_summary(
        self, user_id: str, db: Session
    ) -> dict[str, Decimal]:
        results = (
            db.query(
                Transaction.ai_category,
                func.sum(Transaction.amount).label("total"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.DEBIT,
                Transaction.ai_category.isnot(None),
            )
            .group_by(Transaction.ai_category)
            .all()
        )

        return {category: total for category, total in results if category}


transaction_service = TransactionService()

