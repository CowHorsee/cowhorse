import logging

from fastapi import FastAPI

from api.v1.router import api_router
from core.logging_middleware import log_http_payloads


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    else:
        root_logger.setLevel(logging.INFO)

    logging.getLogger("cowhorse.http").setLevel(logging.INFO)


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