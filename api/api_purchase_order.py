import logging
import json
import azure.functions as func
from azure_functions_openapi.decorator import openapi
from scripts.purchase_order import create_po, get_po_ticket, get_po_details, update_po_status

bp = func.Blueprint(name='purchase_order_api', url_prefix='/po')

import asyncio
from sharedlib.pdf_helper.pdf import generate_po_doc
from sharedlib.email_helper.email import quick_send
from sharedlib.db_helper.db_ops import DBHelper

@bp.route(route="create_po", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Create purchase order",
    description="Generates one or more Purchase Orders from a single Purchase Request. If the PR contains items from multiple suppliers, separate POs are created automatically. Triggers PDF generation and supplier notification.",
    tags=["Purchase Order"],
    route="/api/po/create_po",
    method="POST",
    request_body={"type": "object", "required": ["pr_id", "proc_item", "user_id"], "properties": {
        "pr_id": {"type": "string", "description": "ID of the source Purchase Request"},
        "proc_item": {"type": "array", "items": {"type": "object", "properties": {
            "item_name": {"type": "string"},
            "quantity": {"type": "integer"}
        }}, "description": "List of items and quantities to include in the order(s)"},
        "user_id": {"type": "string", "format": "uuid", "description": "ID of the officer issuing the PO"}
    }},
    response={
        200: {
            "description": "PO(s) created successfully",
            "content": {"application/json": {"schema": {"type": "array", "items": {"type": "string"}, "example": ["PO_202603_00001", "PO_202603_00002"]}}}
        },
        400: {"description": "Validation failed: items not found or unauthorized PR access"}
    }
)
async def api_create_po(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        result = create_po(body.get('pr_id'), body.get('proc_item'), body.get('user_id'))
        
        # Integrate PDF Generation (result is a list of po_ids)
        if isinstance(result, list):
            db = DBHelper()
            # 1. Get Officer Email (Creator)
            officer_df = db.extract("user", conditions={"user_id": body.get('user_id')})
            officer_email = officer_df.iloc[0]['email'] if not officer_df.empty else None
            
            # 2. Get All Managers (To CC)
            roles = db.extract("dim_role", conditions={"role_name": "Procurement Manager"})
            manager_emails = []
            if not roles.empty:
                manager_role_id = roles.iloc[0]['role_id']
                managers = db.extract("user", conditions={"role_id": int(manager_role_id)})
                manager_emails = managers['email'].tolist() if not managers.empty else []

            for po_id in result:
                try:
                    pdf_path = await generate_po_doc(po_id)
                    
                    # Get Supplier Email for this PO
                    po_header = db.extract("purchase_order", conditions={"po_id": po_id})
                    if not po_header.empty:
                        supplier_id = po_header.iloc[0]['supplier_id']
                        supplier_df = db.extract("supplier", conditions={"supplier_id": supplier_id})
                        supplier_email = supplier_df.iloc[0]['email'] if not supplier_df.empty else None
                        
                        if supplier_email:
                            quick_send(
                                template_type="PURCHASE_ORDER",
                                recipient_email=supplier_email,
                                subject=f"New Purchase Order: {po_id}",
                                cc_emails=manager_emails + ([officer_email] if officer_email else []),
                                attachments=[pdf_path] if pdf_path else None,
                                doc_id=po_id,
                                date=po_header.iloc[0]['created_at'][:10] if po_header.iloc[0]['created_at'] else "2026-03-08"
                            )
                except Exception as pdf_err:
                    logging.error(f"Failed to generate/send PO PDF/Email for {po_id}: {pdf_err}")
        
        return func.HttpResponse(str(result), status_code=200 if result else 400)
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="get_po_ticket", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Get PO tickets",
    description="Retrieves a list of Purchase Order tickets with enriched status information. Suppliers only see their own orders; Officers see all.",
    tags=["Purchase Order"],
    route="/api/po/get_po_ticket",
    method="GET",
    parameters=[
        {"name": "user_id", "in": "query", "type": "string", "required": True, "description": "ID for role-based filtering"}
    ],
    response={
        200: {
            "description": "List of PO summary tickets",
            "content": {"application/json": {"schema": {"type": "array", "items": {"type": "object"}}}}
        }
    }
)
def api_get_po_ticket(req: func.HttpRequest) -> func.HttpResponse:
    try:
        user_id = req.params.get('user_id')
        result = get_po_ticket(user_id)
        return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="get_po_details", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Get PO details",
    description="Retrieves the full structural data for a PO including header info and specific itemized line items.",
    tags=["Purchase Order"],
    route="/api/po/get_po_details",
    method="GET",
    parameters=[
        {"name": "user_id", "in": "query", "type": "string", "required": True, "description": "ID for authorization check"},
        {"name": "po_id", "in": "query", "type": "string", "required": True, "description": "ID of the PO to retrieve"}
    ],
    response={
        200: {
            "description": "Detailed PO data",
            "content": {"application/json": {"schema": {"type": "object", "properties": {
                "header": {"type": "object"},
                "items": {"type": "array", "items": {"type": "object"}}
            }}}}
        },
        403: {"description": "Access denied for this po_id"}
    }
)
def api_get_po_details(req: func.HttpRequest) -> func.HttpResponse:
    try:
        user_id = req.params.get('user_id')
        po_id = req.params.get('po_id')
        result = get_po_details(user_id, po_id)
        return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="update_po_status", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Update PO status",
    description="Allows a Supplier to update the status of an order (e.g., 'Awaiting Warehouse', 'Shipped'). Rules vary by current status.",
    tags=["Purchase Order"],
    route="/api/po/update_po_status",
    method="POST",
    request_body={"type": "object", "required": ["supplier_id", "po_id", "status_name"], "properties": {
        "supplier_id": {"type": "string", "format": "uuid", "description": "ID of the supplier performing the update"},
        "po_id": {"type": "string", "description": "ID of the PO"},
        "status_name": {"type": "string", "enum": ["Awaiting Warehouse", "Shipped", "Delivered"], "description": "Target status name"}
    }},
    response={
        200: {"description": "PO status successfully transitioned"},
        400: {"description": "Invalid status transition or unauthorized supplier"}
    }
)
def api_update_po_status(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        result = update_po_status(body.get('supplier_id'), body.get('po_id'), body.get('status_name'))
        return func.HttpResponse(str(result), status_code=200 if result == True else 400)
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)
