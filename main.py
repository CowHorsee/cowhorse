import logging

from fastapi import FastAPI

from api.v1.router import api_router
from core.logging_middleware import log_http_payloads


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


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="CowHorse API",
        version="2.0.0",
        openapi_url="/openapi.json",
        docs_url="/docs",
    )

    app.middleware("http")(log_http_payloads)
    app.include_router(api_router)

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