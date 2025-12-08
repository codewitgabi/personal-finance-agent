from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from api.v1.models.user import User
from api.v1.schemas.auth import (
    UserCreate,
    UserLogin,
)
from api.v1.services.auth import auth_service
from api.v1.services.user import user_service, oauth2_scheme
from api.v1.utils.dependencies import get_db
from api.v1.responses.success_response import success_response

auth = APIRouter(prefix="/auth", tags=["Authentication"])


@auth.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    data = auth_service.create_user(user_data, db)

    return success_response(
        status_code=status.HTTP_201_CREATED,
        message="User created successfully",
        data=data.model_dump(),
    )


@auth.post(
    "/login",
    status_code=status.HTTP_200_OK,
)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    token_data = auth_service.login_user(credentials.email, credentials.password, db)

    return success_response(
        message="Login successful",
        data=token_data.model_dump(),
    )


@auth.post(
    "/logout",
    status_code=status.HTTP_200_OK,
)
async def logout(
    current_user: User = Depends(user_service.get_current_user),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    auth_service.logout_user(token, db)

    return success_response(
        message="Logout successful",
    )
