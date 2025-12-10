from typing import Annotated, Optional
from decimal import Decimal
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import select
from jwt.exceptions import InvalidTokenError
from api.v1.models.user import User
from api.v1.models.blacklisted_token import BlacklistedToken
from api.v1.utils.dependencies import get_db
from api.v1.utils.logger import get_logger
from api.v1.services.auth import auth_service

logger = get_logger("user_service")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class UserService:
    def __init__(self):
        pass

    def get_user_by_email(self, email: str, db: Session) -> User | None:
        return db.scalar(select(User).where(User.email == email))

    def get_user_by_id(self, user_id: str, db: Session) -> User | None:
        return db.scalar(select(User).where(User.id == user_id))

    def update_user_profile(
        self,
        user_id: str,
        monthly_income: Optional[Decimal] = None,
        savings_goal: Optional[Decimal] = None,
        currency: Optional[str] = None,
        db: Session = None,
    ) -> Optional[User]:
        user = self.get_user_by_id(user_id, db)
        if not user:
            return None

        if monthly_income is not None:
            user.monthly_income = monthly_income
        if savings_goal is not None:
            user.savings_goal = savings_goal
        if currency is not None:
            user.currency = currency

        db.commit()
        db.refresh(user)

        logger.info(
            "User profile updated",
            extra={
                "user_id": user_id,
                "monthly_income": str(monthly_income) if monthly_income else None,
                "savings_goal": str(savings_goal) if savings_goal else None,
                "currency": currency,
            },
        )

        return user

    def update_user_profile(
        self,
        user_id: str,
        monthly_income: Optional[Decimal] = None,
        savings_goal: Optional[Decimal] = None,
        currency: Optional[str] = None,
        db: Session = None,
    ) -> Optional[User]:
        user = self.get_user_by_id(user_id, db)
        if not user:
            return None

        if monthly_income is not None:
            user.monthly_income = monthly_income
        if savings_goal is not None:
            user.savings_goal = savings_goal
        if currency is not None:
            user.currency = currency

        db.commit()
        db.refresh(user)

        logger.info(
            "User profile updated",
            extra={
                "user_id": user_id,
                "monthly_income": str(monthly_income) if monthly_income else None,
                "savings_goal": str(savings_goal) if savings_goal else None,
                "currency": currency,
            },
        )

        return user

    def get_current_user(
        self,
        token: Annotated[str, Depends(oauth2_scheme)],
        db: Session = Depends(get_db),
    ) -> User:
        credential_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            payload = auth_service.verify_token(token, db)
            if not payload:
                raise credential_exception

            email: str = payload.get("email")
            if not email:
                raise credential_exception
        except InvalidTokenError:
            raise credential_exception

        blacklisted = db.scalar(
            select(BlacklistedToken).where(BlacklistedToken.token == token)
        )
        if blacklisted:
            raise credential_exception

        user = self.get_user_by_email(email, db)
        if not user:
            raise credential_exception

        return user


user_service = UserService()
