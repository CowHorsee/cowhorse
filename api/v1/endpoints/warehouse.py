from fastapi import APIRouter, HTTPException, Query

from schemas.base import APIResponse, success_response
from schemas.warehouse import UpdateInventoryRequest
from services.warehouse_management import count_inventory, update_inventory

router = APIRouter(prefix="/warehouse", tags=["Warehouse"])


@router.get("/count_inventory", response_model=APIResponse)
def api_count_inventory(item_name: str | None = Query(default=None)):
    try:
        return success_response(
            data=count_inventory(item_name),
            message="Inventory count retrieved successfully",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/update_inventory", response_model=APIResponse)
def api_update_inventory(body: UpdateInventoryRequest):
    try:
        result = update_inventory(body.incoming_csv_path)
        if "item_id" in result:
            return success_response(data=result, message="Inventory updated successfully")
        raise HTTPException(status_code=400, detail=result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc