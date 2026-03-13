from fastapi import APIRouter, HTTPException, Query

from api.schema.schema_base import ERROR_RESPONSES, success_response
from api.schema.schema_warehouse import CountInventoryResponse, UpdateInventoryRequest, UpdateInventoryResponse
from services.warehouse import count_inventory, update_inventory

router = APIRouter(prefix="/warehouse", tags=["Warehouse"])


@router.get("/count_inventory", response_model=CountInventoryResponse, responses=ERROR_RESPONSES)
def api_count_inventory(item_name: str | None = Query(default=None)):
    return success_response(
        message="Inventory count retrieved successfully",
        data=count_inventory(item_name),
    )


@router.post("/update_inventory", response_model=UpdateInventoryResponse, responses=ERROR_RESPONSES)
def api_update_inventory(body: UpdateInventoryRequest):
    result = update_inventory(body.csv_content)
    return success_response(message="Inventory updated successfully", data=result)
