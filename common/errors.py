"""Lỗi ứng dụng và handler trả {error_code, message, details} (docs/api.md mục 2)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from common.constants import ERROR_HTTP_STATUS, ErrorCode

log = logging.getLogger("api.errors")


class AppError(Exception):
    """Lỗi nghiệp vụ. `rule` là mã quy tắc trong đặc tả (ví dụ "BH-02"), đưa vào details.rule."""

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        *,
        rule: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = ErrorCode(error_code)
        self.message = message
        self.details: dict[str, Any] = dict(details or {})
        if rule is not None:
            self.details["rule"] = rule


def error_response(
    error_code: ErrorCode, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=ERROR_HTTP_STATUS[error_code],
        content={
            "error_code": str(error_code),
            "message": message,
            "details": jsonable_encoder(details or {}),
        },
    )


# Lỗi do framework ném ra (route không tồn tại, sai method…) cũng trả đúng dạng chung
_HTTP_STATUS_TO_CODE: dict[int, ErrorCode] = {
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.error_code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(
            ErrorCode.VALIDATION_ERROR, "Dữ liệu gửi lên không hợp lệ", {"errors": exc.errors()}
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_STATUS_TO_CODE.get(exc.status_code, ErrorCode.VALIDATION_ERROR)
        response = error_response(code, str(exc.detail))
        response.status_code = exc.status_code
        return response

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("Lỗi không lường trước", exc_info=exc)
        return error_response(ErrorCode.INTERNAL_ERROR, "Lỗi hệ thống")
