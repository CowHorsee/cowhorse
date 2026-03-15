from fastapi import APIRouter, HTTPException, Query

from api.schema.schema_base import ERROR_RESPONSES, success_response
from api.schema.schema_warehouse import CountInventoryResponse, UpdateInventoryRequest, UpdateInventoryResponse, GraphDatapointResponse
from services.warehouse import count_inventory, update_inventory, get_graph_datapoint

router = APIRouter(prefix="/warehouse", tags=["Warehouse"])


@router.get(
    "/count_inventory", 
    response_model=CountInventoryResponse, 
    responses=ERROR_RESPONSES,
    description="Endpoint to count inventory items. If query is provided, returns items matching item_id or item_name. If no query is provided, returns count for all items."

    )
def api_count_inventory(query: str | None = Query(default=None, alias="item_name")):
    return success_response(
        message="Inventory count retrieved successfully",
        data=count_inventory(query),
    )


@router.post("/update_inventory", response_model=UpdateInventoryResponse, responses=ERROR_RESPONSES)
def api_update_inventory(body: UpdateInventoryRequest):
    result = update_inventory(body.csv_content)
    return success_response(message="Inventory updated successfully", data=result)


@router.get(
    "/graph_datapoint",
    response_model=GraphDatapointResponse,
    responses=ERROR_RESPONSES,
    description="Endpoint to get inventory count and predicted demand for an item on a specific month to render a graph. Includes actual sales for past months."
)
def api_get_graph_datapoint(
    item_name: str = Query(..., description="Name of the item to query"),
    year: int = Query(..., ge=2026, description="Year to query (e.g. 2026)"),
    month: int = Query(..., ge=1, le=12, description="Month to query (1-12)")
):
    return success_response(
        message="Graph datapoint retrieved successfully",
        data=get_graph_datapoint(item_name, year, month),
    )
