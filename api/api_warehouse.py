import logging
import json
import azure.functions as func
from azure_functions_openapi.decorator import openapi
from scripts.uat_warehouse_management import count_inventory, update_inventory

bp = func.Blueprint(name='warehouse_api', url_prefix='/warehouse')

@bp.route(route="count_inventory", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Count inventory",
    description="Retrieves the current stock level for a specific item or all items from the warehouse stock table.",
    tags=["Warehouse"],
    route="/api/warehouse/count_inventory",
    method="GET",
    parameters=[
        {"name": "item_name", "in": "query", "type": "string", "description": "Optional name of a specific item to count"}
    ],
    response={
        200: {
            "description": "Stock levels retrieved",
            "content": {"application/json": {"schema": {"oneOf": [
                {"type": "integer", "description": "Quantity if item_name provided"},
                {"type": "array", "items": {"type": "object"}, "description": "Full stock list if item_name omitted"}
            ]}}}
        }
    }
)
def api_count_inventory(req: func.HttpRequest) -> func.HttpResponse:
    try:
        item_name = req.params.get('item_name')
        result = count_inventory(item_name)
        return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="update_inventory", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Update inventory from CSV",
    description="Processes an incoming stock CSV file (e.g., from a delivery) and updates the warehouse stock quantities in Azure Table Storage.",
    tags=["Warehouse"],
    route="/api/warehouse/update_inventory",
    method="POST",
    request_body={"type": "object", "required": ["incoming_csv_path"], "properties": {
        "incoming_csv_path": {"type": "string", "description": "Absolute path to the delivery/warehouse CSV file"}
    }},
    response={
        200: {"description": "Inventory successfully updated and stock levels reconciled"},
        400: {"description": "CSV file not found or invalid format"}
    }
)
def api_update_inventory(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        result = update_inventory(body.get('incoming_csv_path'))
        return func.HttpResponse(result, status_code=200 if "item_id" in result else 400)
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)
