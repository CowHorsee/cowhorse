from fastapi import APIRouter, HTTPException, Query

from schemas.warehouse import UpdateInventoryRequest
from services.warehouse_management import count_inventory, update_inventory

router = APIRouter(prefix="/warehouse", tags=["Warehouse"])


@router.get("/count_inventory")
def api_count_inventory(item_name: str | None = Query(default=None)):
    try:
        return count_inventory(item_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/update_inventory")
def api_update_inventory(body: UpdateInventoryRequest):
    try:
        result = update_inventory(body.incoming_csv_path)
        if "item_id" in result:
            return result
        raise HTTPException(status_code=400, detail=result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
