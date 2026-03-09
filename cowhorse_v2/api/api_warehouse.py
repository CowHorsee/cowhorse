import json
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from scripts.uat_warehouse_management import count_inventory, update_inventory

router = APIRouter(prefix="/api/warehouse", tags=["Warehouse"])


@router.get("/count_inventory")
def api_count_inventory(item_name: str | None = Query(default=None)):
    try:
        result = count_inventory(item_name)
        return JSONResponse(json.loads(json.dumps(result)), status_code=200)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/update_inventory")
def api_update_inventory(body: dict[str, Any]):
    try:
        result = update_inventory(body.get("incoming_csv_path"))
        status = 200 if "item_id" in result else 400
        return PlainTextResponse(result, status_code=status)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
