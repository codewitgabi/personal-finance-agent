import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from api.v1.models.user import User
from api.v1.models.blacklisted_token import BlacklistedToken
from api.v1.schemas.auth import UserCreate, UserResponse, TokenResponse
from api.v1.utils.logger import get_logger

logger = get_logger("auth_service")


class AuthService:
    def __init__(self):
        self.ph = PasswordHasher()
        self.secret_key = os.environ.get("JWT_SECRET_KEY")
        self.algorithm = "HS256"
        self.access_token_expire_hours = int(
            os.environ.get("ACCESS_TOKEN_EXPIRE_HOURS", 3)
        )

    def hash_password(self, password: str) -> str:
        return self.ph.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            self.ph.verify(hashed_password, plain_password)
            return True
        except VerifyMismatchError:
            return False

    def create_access_token(
        self, data: dict, expires_delta: Optional[timedelta] = None
    ) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                hours=self.access_token_expire_hours
            )

        to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str, db: Session) -> Optional[dict]:
        try:
            blacklisted = db.scalar(
                select(BlacklistedToken).where(BlacklistedToken.token == token)
            )
            if blacklisted:
                return None

            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except InvalidTokenError:
            return None

    def create_user(self, user_data: UserCreate, db: Session) -> UserResponse:
        existing_user = db.scalar(
            select(User).where(
                (User.email == user_data.email) | (User.username == user_data.username)
            )
        )

        if existing_user:
            if existing_user.email == user_data.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken",
                )

        hashed_password = self.hash_password(user_data.password)

        new_user = User(
            username=user_data.username,
            email=user_data.email,
            password=hashed_password,
            currency=user_data.currency or "USD",
            monthly_income=user_data.monthly_income,
            savings_goal=user_data.savings_goal,
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        logger.info(
            "User created",
            extra={
                "user_id": new_user.id,
                "email": new_user.email,
                "username": new_user.username,
            },
        )

        return UserResponse.model_validate(new_user)

    def authenticate_user(
        self, email: str, password: str, db: Session
    ) -> Optional[User]:
        user = db.scalar(select(User).where(User.email == email))

        if not user:
            return None

        if not self.verify_password(password, user.password):
            return None

        return user

    def login_user(self, email: str, password: str, db: Session) -> TokenResponse:
        user = self.authenticate_user(email, password, db)

        if not user:
            logger.warning("Login failed", extra={"email": email})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        access_token_expires = timedelta(hours=self.access_token_expire_hours)
        access_token = self.create_access_token(
            data={"sub": user.id, "email": user.email},
            expires_delta=access_token_expires,
        )

        logger.info(
            "User logged in",
            extra={
                "user_id": user.id,
                "email": user.email,
            },
        )

        return TokenResponse(access_token=access_token)

    def logout_user(self, token: str, db: Session) -> None:
        payload = self.verify_token(token, db)

        if payload:
            existing = db.scalar(
                select(BlacklistedToken).where(BlacklistedToken.token == token)
            )
            if existing:
                logger.info(
                    "Token already blacklisted", extra={"user_id": payload.get("sub")}
                )
                return

            expires_at = datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc)
            blacklisted_token = BlacklistedToken(token=token, expires_at=expires_at)
            db.add(blacklisted_token)
            db.commit()

            logger.info("User logged out", extra={"user_id": payload.get("sub")})


auth_service = AuthService()
