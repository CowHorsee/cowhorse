import logging
import json
import azure.functions as func
from azure_functions_openapi.decorator import openapi
from scripts.purchase_request import (
    create_pr, accept_pr_suggestion, modify_pr, 
    get_pr_ticket, get_pr_details, review_pr, procurement_alert
)

bp = func.Blueprint(name='purchase_request_api', url_prefix='/pr')

import asyncio
from sharedlib.pdf_helper.pdf import generate_pr_doc
from sharedlib.email_helper.email import quick_send
from sharedlib.db_helper.db_ops import DBHelper

@bp.route(route="create_pr", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Create purchase request",
    description="Submits a new purchase request for procurement. Triggers automated PDF generation and manager notification upon success.",
    tags=["Purchase Request"],
    route="/api/pr/create_pr",
    method="POST",
    request_body={"type": "object", "required": ["user_id", "proc_item", "justification"], "properties": {
        "user_id": {"type": "string", "format": "uuid", "description": "ID of the procurement officer creating the request"},
        "proc_item": {"type": "object", "additionalProperties": {"type": "integer"}, "description": "Mapping of item names to requested quantities", "example": {"Elba Built-in Gas Hob": 10, "Faber Chimney Hood": 5}},
        "justification": {"type": "string", "description": "Business reason for the procurement request"}
    }},
    response={
        200: {
            "description": "PR created and notifications triggered",
            "content": {"application/json": {"schema": {"type": "object", "properties": {
                "pr_id": {"type": "string", "example": "PR_202603_00001"},
                "status": {"type": "integer", "example": 2, "description": "2 = Pending Review"},
                "items": {"type": "array", "items": {"type": "object"}}
            }}}}
        },
        400: {"description": "Invalid items or incomplete request body"}
    }
)
async def api_create_pr(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        result = create_pr(body.get('user_id'), body.get('proc_item'), body.get('justification'))
        
        # Integrate PDF Generation
        if isinstance(result, dict) and "pr_id" in result:
            pr_id = result["pr_id"]
            try:
                pdf_path = await generate_pr_doc(pr_id)
                
                # Integration 4: Send PR notification email
                db = DBHelper()
                # 1. Get Officer Email (Creator)
                officer_df = db.extract("user", conditions={"user_id": body.get('user_id')})
                officer_email = officer_df.iloc[0]['email'] if not officer_df.empty else None
                officer_name = officer_df.iloc[0]['name'] if not officer_df.empty else "Officer"
                
                # 2. Get All Managers (To recipients)
                roles = db.extract("dim_role", conditions={"role_name": "Procurement Manager"})
                if not roles.empty:
                    manager_role_id = roles.iloc[0]['role_id']
                    managers = db.extract("user", conditions={"role_id": int(manager_role_id)})
                    manager_emails = managers['email'].tolist() if not managers.empty else []
                    
                    if manager_emails:
                        # Fetch item count for the template
                        proc_item = body.get('proc_item', {})
                        item_count = sum(proc_item.values()) if isinstance(proc_item, dict) else 0

                        quick_send(
                            template_type="PURCHASE_REQUEST",
                            recipient_email=manager_emails[0], # Send to first manager
                            subject=f"Action Required: New Purchase Request {pr_id}",
                            cc_emails=manager_emails[1:] + ([officer_email] if officer_email else []),
                            attachments=[pdf_path] if pdf_path else None,
                            doc_id=pr_id,
                            officer_name=officer_name,
                            item_count=item_count
                        )
            except Exception as pdf_err:
                logging.error(f"Failed to generate/send PR PDF/Email: {pdf_err}")

        return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="accept_pr_suggestion", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Accept AI PR suggestion",
    description="Converts an AI-generated procurement suggestion (Status 1) into a standard Purchase Request (Status 2) by associating it with a responsible officer.",
    tags=["Purchase Request"],
    route="/api/pr/accept_pr_suggestion",
    method="POST",
    request_body={"type": "object", "required": ["pr_id", "officer_id"], "properties": {
        "pr_id": {"type": "string", "description": "ID of the AI suggestion (PR_...) to accept"},
        "officer_id": {"type": "string", "format": "uuid", "description": "ID of the officer taking responsibility for the request"}
    }},
    response={
        200: {"description": "AI suggestion accepted and converted to standard PR"},
        400: {"description": "PR is not a suggestion or invalid IDs provided"}
    }
)
def api_accept_pr_suggestion(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        result = accept_pr_suggestion(body.get('pr_id'), body.get('officer_id'))
        return func.HttpResponse(result, status_code=200 if "Success" in result else 400)
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="modify_pr", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Modify purchase request",
    description="Updates the items or justification of a PR. Rules: Officers can only modify AI suggestions (Status 1). Managers can modify submitted requests (Status 2).",
    tags=["Purchase Request"],
    route="/api/pr/modify_pr",
    method="POST",
    request_body={"type": "object", "required": ["user_id", "pr_id", "proc_item", "justification"], "properties": {
        "user_id": {"type": "string", "format": "uuid", "description": "ID of the user performing the modification"},
        "pr_id": {"type": "string", "description": "ID of the target PR"},
        "proc_item": {"type": "object", "additionalProperties": {"type": "integer"}, "description": "New item mapping (replaces old items)"},
        "justification": {"type": "string", "description": "Updated justification text"}
    }},
    response={
        200: {"description": "PR updated successfully and audit log recorded"},
        400: {"description": "Modification not allowed due to current status or role restrictions"}
    }
)
def api_modify_pr(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        result = modify_pr(body.get('user_id'), body.get('pr_id'), body.get('proc_item'), body.get('justification'))
        return func.HttpResponse(result, status_code=200 if "Success" in result else 400)
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="get_pr_ticket", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Get PR tickets",
    description="Retrieves a list of PR tickets with enriched status names and creator role info for the dashboard view.",
    tags=["Purchase Request"],
    route="/api/pr/get_pr_ticket",
    method="GET",
    parameters=[
        {"name": "user_id", "in": "query", "type": "string", "description": "Filter by creator (required for Officers to see their own)"},
        {"name": "pr_id", "in": "query", "type": "string", "description": "Optional specific PR ID filter"},
        {"name": "status", "in": "query", "type": "integer", "description": "Filter by status_id (1=AI, 2=Pending, 3=Rejected, 4=Approved)"}
    ],
    response={
        200: {
            "description": "Enriched tickets retrieved",
            "content": {"application/json": {"schema": {"type": "array", "items": {"type": "object"}}}}
        }
    }
)
def api_get_pr_ticket(req: func.HttpRequest) -> func.HttpResponse:
    try:
        user_id = req.params.get('user_id')
        pr_id = req.params.get('pr_id')
        status = req.params.get('status')
        result = get_pr_ticket(user_id, pr_id, status)
        return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="get_pr_details", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Get PR details",
    description="Retrieves the full structural data for a PR, including header and all bridged line items.",
    tags=["Purchase Request"],
    route="/api/pr/get_pr_details",
    method="GET",
    parameters=[
        {"name": "user_id", "in": "query", "type": "string", "required": True, "description": "ID for authorization check"},
        {"name": "pr_id", "in": "query", "type": "string", "required": True, "description": "ID of the PR to retrieve"}
    ],
    response={
        200: {
            "description": "Detailed PR data",
            "content": {"application/json": {"schema": {"type": "object", "properties": {
                "header": {"type": "object"},
                "items": {"type": "array", "items": {"type": "object"}}
            }}}}
        },
        403: {"description": "Unauthorized to view this PR"}
    }
)
def api_get_pr_details(req: func.HttpRequest) -> func.HttpResponse:
    try:
        user_id = req.params.get('user_id')
        pr_id = req.params.get('pr_id')
        result = get_pr_details(user_id, pr_id)
        return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="review_pr", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Review purchase request",
    description="Allows a Manager to Approve or Reject a PR. Status 2 -> (4 or 3).",
    tags=["Purchase Request"],
    route="/api/pr/review_pr",
    method="POST",
    request_body={"type": "object", "required": ["pr_id", "decision", "manager_id"], "properties": {
        "pr_id": {"type": "string", "description": "ID of the PR to review"},
        "decision": {"type": "string", "enum": ["approve", "reject"], "description": "Manager's decision"},
        "manager_id": {"type": "string", "format": "uuid", "description": "Manager performing the review"}
    }},
    response={
        200: {"description": "PR status updated and reviewer logged"},
        403: {"description": "User is not a Manager"},
        400: {"description": "PR is not in a pending state or invalid ID"}
    }
)
def api_review_pr(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        result = review_pr(body.get('pr_id'), body.get('decision'), body.get('manager_id'))
        return func.HttpResponse(result, status_code=200 if "Success" in result or " PR " in result else 400)
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="procurement_alert", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Trigger procurement alert (AI)",
    description="Simulates an AI detecting low stock. If predicted demand vs current stock exceeds 80%, an automated PR suggestion (Status 1) is created and Officers are notified.",
    tags=["Purchase Request"],
    route="/api/pr/procurement_alert",
    method="POST",
    request_body={"type": "object", "required": ["item_name", "predicted_demand", "justification"], "properties": {
        "item_name": {"type": "string", "description": "Name of the item to check"},
        "predicted_demand": {"type": "number", "description": "Expected demand quantity"},
        "justification": {"type": "string", "description": "AI-generated reasoning for the alert"}
    }},
    response={
        200: {
            "description": "Alert processed. May return standard PR result or notification of sufficient stock.",
            "content": {"application/json": {"schema": {"oneOf": [
                {"type": "object", "description": "Standard PR result if triggered"},
                {"type": "string", "example": "Stock level sufficient. No PR triggered."}
            ]}}}
        }
    }
)
def api_procurement_alert(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        result = procurement_alert(body.get('item_name'), body.get('predicted_demand'), body.get('justification'))
        return func.HttpResponse(json.dumps(result) if isinstance(result, dict) else result, status_code=200)
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)
