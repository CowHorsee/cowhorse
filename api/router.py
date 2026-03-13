from fastapi import APIRouter

from api.api_data_loader import router as data_loader_router
from api.api_po import router as purchase_orders_router
from api.api_pr import router as purchase_requests_router
from api.api_user import router as users_router
from api.api_warehouse import router as warehouse_router

api_router = APIRouter(prefix="/api")

api_router.include_router(users_router)
api_router.include_router(purchase_requests_router)
api_router.include_router(purchase_orders_router)
api_router.include_router(warehouse_router)
api_router.include_router(data_loader_router)
