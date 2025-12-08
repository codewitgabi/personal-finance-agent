from fastapi import status
from pydantic import BaseModel


class ValidationErrorResponse(BaseModel):
    success: bool = False
    status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY
    message: str = "Validation error"
    errors: list


class ErrorResponse(BaseModel):
    success: bool = False
    status_code: int
    message: str
