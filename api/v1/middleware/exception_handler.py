from fastapi import Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError, DatabaseError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException
from api.v1.utils.logger import get_logger

logger = get_logger("exception_handler")


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        errors.append(
            {
                "field": field if field else "body",
                "message": error["msg"],
                "type": error["type"],
            }
        )

    request_id = getattr(request.state, "request_id", None)
    logger.warning(
        "Validation error",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "errors": errors,
        },
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder(
            {
                "success": False,
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "message": "Validation error",
                "errors": errors,
            }
        ),
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    logger.warning(
        "HTTP exception",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
            "detail": exc.detail,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(
            {"success": False, "status_code": exc.status_code, "message": exc.detail}
        ),
    )


async def integrity_error_handler(request: Request, exc: IntegrityError):
    error_message = (
        str(exc.orig) if exc.orig else "Database integrity constraint violation"
    )

    if "UNIQUE constraint" in error_message or "duplicate key" in error_message.lower():
        message = "Resource already exists"
    elif (
        "FOREIGN KEY constraint" in error_message
        or "foreign key" in error_message.lower()
    ):
        message = "Referenced resource does not exist"
    elif "NOT NULL constraint" in error_message:
        message = "Required field cannot be null"
    else:
        message = "Database constraint violation"

    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "Database integrity error",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "error_message": error_message,
            "response_message": message,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder(
            {
                "success": False,
                "status_code": status.HTTP_400_BAD_REQUEST,
                "message": message,
            }
        ),
    )


async def database_error_handler(request: Request, exc: DatabaseError):
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "Database error",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "error_type": type(exc).__name__,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=jsonable_encoder(
            {
                "success": False,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "Database operation failed",
            }
        ),
    )


async def operational_error_handler(request: Request, exc: OperationalError):
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "Database operational error",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=jsonable_encoder(
            {
                "success": False,
                "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
                "message": "Database service unavailable",
            }
        ),
    )


async def starlette_http_exception_handler(
    request: Request, exc: StarletteHTTPException
):
    message = exc.detail if exc.detail else "Not Found"
    if exc.status_code == 404:
        message = "Resource not found"
    elif exc.status_code == 405:
        message = "Method not allowed"
    elif exc.status_code == 403:
        message = "Forbidden"
    elif exc.status_code == 401:
        message = "Unauthorized"

    request_id = getattr(request.state, "request_id", None)
    log_level = "warning" if exc.status_code < 500 else "error"
    getattr(logger, log_level)(
        "HTTP exception",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
            "response_message": message,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(
            {"success": False, "status_code": exc.status_code, "message": message}
        ),
    )


async def general_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "Unexpected error",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=jsonable_encoder(
            {
                "success": False,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "message": "An unexpected error occurred",
            }
        ),
    )
