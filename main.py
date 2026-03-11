import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.v1.router import api_router
from core.logging_middleware import log_http_payloads
from schemas.base import error_response


def configure_logging() -> None:
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not root_logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    server_logger = logging.getLogger("gunicorn.error")
    if not server_logger.handlers:
        uvicorn_logger = logging.getLogger("uvicorn.error")
        if uvicorn_logger.handlers:
            server_logger = uvicorn_logger

    http_logger = logging.getLogger("cowhorse.http")
    http_logger.setLevel(logging.INFO)

    if server_logger.handlers:
        http_logger.handlers = server_logger.handlers[:]
        http_logger.propagate = False
    else:
        http_logger.propagate = True

    for handler in http_logger.handlers:
        handler.setLevel(logging.INFO)
        if handler.formatter is None:
            handler.setFormatter(formatter)


def _normalize_validation_errors(exc: RequestValidationError) -> list[str]:
    errors: list[str] = []

    for error in exc.errors():
        location = " -> ".join(str(item) for item in error.get("loc", []))
        message = str(error.get("msg", "Invalid request"))
        errors.append(f"{location}: {message}" if location else message)

    return errors or ["Invalid request"]


def _normalize_http_error(detail: object) -> list[str]:
    if isinstance(detail, str):
        return [detail]

    if isinstance(detail, list):
        normalized: list[str] = []
        for item in detail:
            if isinstance(item, dict) and "msg" in item:
                location = " -> ".join(str(part) for part in item.get("loc", []))
                message = str(item["msg"])
                normalized.append(f"{location}: {message}" if location else message)
            else:
                normalized.append(str(item))
        return normalized or ["Request failed"]

    if isinstance(detail, dict):
        return [str(detail)]

    return ["Request failed"]


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="CowHorse API",
        version="2.1.1",
        description="Last updated: 2026-03-11 03:05 MYT",
        openapi_url="/openapi.json",
        docs_url="/docs",
    )

    app.middleware("http")(log_http_payloads)
    app.include_router(api_router)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        errors = _normalize_http_error(exc.detail)
        message = errors[0] if len(errors) == 1 else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(message=message, errors=errors).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        errors = _normalize_validation_errors(exc)
        return JSONResponse(
            status_code=422,
            content=error_response(message="Validation failed", errors=errors).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception):
        logging.exception("Unhandled exception while processing request", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_response(
                message="Internal server error",
                errors=[str(exc)],
            ).model_dump(),
        )

    @app.get("/")
    def root():
        return {
            "message": "Welcome to Donki-Wonki API",
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health")
    def health_check():
        return {"status": "healthy"}

    return app


app = create_app()