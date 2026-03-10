from fastapi import APIRouter

from api.v1.endpoints.data_loader import router as data_loader_router
from api.v1.endpoints.purchase_orders import router as purchase_orders_router
from api.v1.endpoints.purchase_requests import router as purchase_requests_router
from api.v1.endpoints.users import router as users_router
from api.v1.endpoints.warehouse import router as warehouse_router

api_router = APIRouter(prefix="/api")

api_router.include_router(users_router)
api_router.include_router(purchase_requests_router)
api_router.include_router(purchase_orders_router)
api_router.include_router(warehouse_router)
api_router.include_router(data_loader_router)
