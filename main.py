import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, DatabaseError, OperationalError
import uvicorn

from api.v1.responses.success_response import success_response
from api.v1.utils.database import Base, engine
from api.v1.utils.logger import setup_logger
from api.v1.middleware.logging_middleware import LoggingMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from api.v1.middleware.exception_handler import (
    validation_exception_handler,
    integrity_error_handler,
    database_error_handler,
    operational_error_handler,
    starlette_http_exception_handler,
    general_exception_handler,
)

load_dotenv()

setup_logger()


# create database tables

Base.metadata.create_all(bind=engine)

app: FastAPI = FastAPI(
    debug=os.environ.get("DEBUG") != "False",
    docs_url="/docs",
    redoc_url=None,
    title="Fastapi Langchain API",
)

app.add_middleware(LoggingMiddleware)

# Exception middleware

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(OperationalError, operational_error_handler)
app.add_exception_handler(DatabaseError, database_error_handler)
app.add_exception_handler(Exception, general_exception_handler)

# cors middleware

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def index():
    return success_response(message="Welcome to fastapi-langchain-api")


# start server

if __name__ == "__main__":
    uvicorn.run(app, port=int(os.environ.get("SERVER_PORT", 5001)), reload=False)
