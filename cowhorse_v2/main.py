import sys
from pathlib import Path

from fastapi import FastAPI

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from cowhorse_v2.api.api_data_loader import router as data_loader_router
from cowhorse_v2.api.api_purchase_order import router as purchase_order_router
from cowhorse_v2.api.api_purchase_request import router as purchase_request_router
from cowhorse_v2.api.api_user_management import router as user_management_router
from cowhorse_v2.api.api_warehouse import router as warehouse_router

app = FastAPI(title="CowHorse API", version="2.0.0")

app.include_router(user_management_router)
app.include_router(purchase_request_router)
app.include_router(purchase_order_router)
app.include_router(warehouse_router)
app.include_router(data_loader_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
