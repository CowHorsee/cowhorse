from fastapi import FastAPI
from uvicorn import lifespan

from api.v1.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="CowHorse API",
        version="2.0.0",
        openapi_url="/openapi.json",
        docs_url="/docs",
    )

    app.include_router(api_router)

    @app.get("/health")
    def health_check():
        return {"status": "healthy"}

    return app


app = create_app()