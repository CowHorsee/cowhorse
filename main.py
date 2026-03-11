from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from api.api_user_management import router as user_router
from api.api_purchase_request import router as pr_router
from api.api_purchase_order import router as po_router
from api.api_warehouse import router as warehouse_router
from api.api_data_loader import router as data_loader_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CowHorse Procurement API",
    description="FastAPI refactor of the Azure Functions-based procurement system.",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from pydantic import ValidationError

# Exception handler for Pydantic validation errors
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    logger.error(f"Validation error at {request.url}: {exc.json()}")
    return JSONResponse(
        status_code=422,
        content={"message": "Validation Error", "detail": exc.errors()},
    )

# Exception handler for general errors
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error at {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": str(exc)},
    )

# Include routers
app.include_router(user_router, prefix="/api/user", tags=["User Management"])
app.include_router(pr_router, prefix="/api/pr", tags=["Purchase Request"])
app.include_router(po_router, prefix="/api/po", tags=["Purchase Order"])
app.include_router(warehouse_router, prefix="/api/warehouse", tags=["Warehouse"])
app.include_router(data_loader_router, prefix="/api/data-loader", tags=["Maintenance"])

@app.get("/")
async def root():
    return {"message": "Welcome to CowHorse Procurement API", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
