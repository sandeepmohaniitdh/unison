"""One error format for the whole API.

Every error response has this body:

    {"error": {"code": "TEAM_FULL", "message": "...", "details": {...}, "request_id": "..."}}

`code` is stable and meant for the frontend; `message` is for people.
Services raise AppError; the handlers below turn every exception into this body.
"""

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("unison")


class ErrorInfo(BaseModel):
    code: str = Field(examples=["NOT_FOUND"])
    message: str = Field(examples=["Course not found."])
    details: Any = None
    request_id: str = Field(examples=["4f1c2b9e7a3d4c5e"])


class ErrorBody(BaseModel):
    error: ErrorInfo


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None, headers: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def bad_request(code: str, message: str, details: Any = None) -> AppError:
    return AppError(400, code, message, details)


def unauthorized(message: str = "Please log in.", code: str = "NOT_AUTHENTICATED") -> AppError:
    return AppError(401, code, message)


def forbidden(message: str = "You are not allowed to do this.", code: str = "FORBIDDEN") -> AppError:
    return AppError(403, code, message)


def not_found(what: str = "Item") -> AppError:
    return AppError(404, "NOT_FOUND", f"{what} not found.")


def conflict(code: str, message: str, details: Any = None) -> AppError:
    return AppError(409, code, message, details)


def unprocessable(code: str, message: str, details: Any = None) -> AppError:
    return AppError(422, code, message, details)


def too_many(code: str, message: str, retry_after: int | None = None) -> AppError:
    headers = {"Retry-After": str(retry_after)} if retry_after else None
    details = {"retry_after_seconds": retry_after} if retry_after else None
    return AppError(429, code, message, details, headers)


def unavailable(code: str, message: str) -> AppError:
    return AppError(503, code, message)


def _body(request: Request, code: str, message: str, details: Any = None) -> dict:
    request_id = getattr(request.state, "request_id", "")
    return {"error": {"code": code, "message": message, "details": jsonable_encoder(details), "request_id": request_id}}


HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "NOT_AUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    429: "TOO_MANY_REQUESTS",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        request.state.request_id = incoming[:64] if incoming else uuid.uuid4().hex[:16]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status,
            content=_body(request, exc.code, exc.message, exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in err["loc"][1:]) or str(err["loc"][0]), "problem": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_body(request, "VALIDATION_ERROR", "Some fields are missing or invalid.", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        code = HTTP_CODES.get(exc.status_code, "ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(request, code, message),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unexpected_handler(request: Request, exc: Exception):
        log.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_body(request, "INTERNAL_ERROR", "Something went wrong on our side."),
        )
