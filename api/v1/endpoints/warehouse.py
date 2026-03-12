from fastapi import APIRouter, HTTPException, Query

from api.schemas.base import ERROR_RESPONSES, success_response
from api.schemas.warehouse import CountInventoryResponse, UpdateInventoryRequest, UpdateInventoryResponse
from services.warehouse_management import count_inventory, update_inventory

router = APIRouter(prefix="/warehouse", tags=["Warehouse"])


@router.get("/count_inventory", response_model=CountInventoryResponse, responses=ERROR_RESPONSES)
def api_count_inventory(item_name: str | None = Query(default=None)):
    try:
        return success_response(
            message="Inventory count retrieved successfully",
            data=count_inventory(item_name),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/update_inventory", response_model=UpdateInventoryResponse, responses=ERROR_RESPONSES)
def api_update_inventory(body: UpdateInventoryRequest):
    try:
        result = update_inventory(body.incoming_csv_path)
        if "item_id" in result:
            return success_response(message="Inventory updated successfully", data=result)
        raise HTTPException(status_code=400, detail=result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc