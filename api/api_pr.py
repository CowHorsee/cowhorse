import logging

from fastapi import APIRouter, HTTPException, Query

from api.schema.schema_base import ERROR_RESPONSES, success_response
from api.schema.schema_pr import (
    AcceptPRSuggestionRequest,
    AcceptPRSuggestionResponse,
    CreatePRAPIResponse,
    CreatePRRequest,
    ModifyPRRequest,
    ModifyPRResponse,
    PRDetailsAPIResponse,
    PRTicketListResponse,
    ProcurementAlertRequest,
    ProcurementAlertResponse,
    ReviewPRRequest,
    ReviewPRResponse,
)
from services.pr import (
    accept_pr_suggestion,
    create_pr,
    get_pr_details,
    get_pr_list_by_user_id,
    get_pr_ticket,
    modify_pr,
    procurement_alert,
    review_pr,
)
from services.sharedlib.db_helper.db_helper import DBHelper
from services.sharedlib.email_helper.email_helper import quick_send
from services.sharedlib.pdf_helper.pdf_helper import generate_pr_doc

router = APIRouter(prefix="/pr", tags=["Purchase Request"])


@router.post("/create_pr", response_model=CreatePRAPIResponse, responses=ERROR_RESPONSES)
async def api_create_pr(body: CreatePRRequest):
    result = create_pr(body.user_id, body.proc_item, body.justification)

    if isinstance(result, dict) and "pr_id" in result:
        pr_id = str(result["pr_id"])
        try:
            pdf_path = await generate_pr_doc(pr_id)
            db = DBHelper()
            officer_df = db.extract("user", conditions={"user_id": body.user_id})
            officer_email = officer_df.iloc[0]["email"] if not officer_df.empty else None
            officer_name = officer_df.iloc[0]["name"] if not officer_df.empty else "Officer"

            roles = db.extract("dim_role", conditions={"role_name": "Procurement Manager"})
            if not roles.empty:
                manager_role_id = roles.iloc[0]["role_id"]
                managers = db.extract("user", conditions={"role_id": int(manager_role_id)})
                manager_emails = managers["email"].tolist() if not managers.empty else []
                if manager_emails:
                    item_count = sum(sum(d.values()) for d in body.proc_item)
                    quick_send(
                        template_type="PURCHASE_REQUEST",
                        recipient_email=manager_emails,
                        subject=f"Action Required: New Purchase Request {pr_id}",
                        cc_emails=[officer_email] if officer_email else None,
                        attachments=[pdf_path] if pdf_path else None,
                        doc_id=pr_id,
                        officer_name=officer_name,
                        item_count=item_count,
                    )
        except Exception as pdf_err:
            logging.error(f"Failed to generate/send PR PDF/Email: {pdf_err}")

    return success_response(message="Purchase request created successfully", data=result)


@router.post("/accept_pr_suggestion", response_model=AcceptPRSuggestionResponse, responses=ERROR_RESPONSES)
def api_accept_pr_suggestion(body: AcceptPRSuggestionRequest):
    result = accept_pr_suggestion(body.pr_id, body.officer_id)
    return success_response(message=result, data=result)


@router.post("/modify_pr", response_model=ModifyPRResponse, responses=ERROR_RESPONSES)
def api_modify_pr(body: ModifyPRRequest):
    result = modify_pr(body.user_id, body.pr_id, body.proc_item, body.justification)
    return success_response(message=result, data=result)


@router.get("/get_pr_ticket", response_model=PRTicketListResponse, responses=ERROR_RESPONSES)
def api_get_pr_ticket(
    user_id: str = Query(...),
    pr_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    return success_response(
        message="Purchase requests retrieved successfully",
        data=get_pr_ticket(user_id, pr_id, status),
    )


@router.get("/list_by_user", response_model=PRTicketListResponse, responses=ERROR_RESPONSES)
def api_get_pr_list_by_user(user_id: str = Query(...)):
    return success_response(
        message="Purchase requests retrieved successfully",
        data=get_pr_list_by_user_id(user_id),
    )


@router.get("/get_pr_details", response_model=PRDetailsAPIResponse, responses=ERROR_RESPONSES)
def api_get_pr_details(user_id: str = Query(...), pr_id: str = Query(...)):
    result = get_pr_details(user_id, pr_id)
    return success_response(message="Purchase request details retrieved successfully", data=result)


@router.post(
    "/review_pr", 
    response_model=ReviewPRResponse, 
    responses=ERROR_RESPONSES,
    description="Endpoint for managers to review a purchase request. Pass exactly 'approve', 'approved', 'accept', or 'accepted' in the decision field to approve it. Any other text will reject it."
)
def api_review_pr(body: ReviewPRRequest):
    result = review_pr(body.pr_id, body.decision, body.manager_id)
    return success_response(message=result, data=result)


@router.post(
    "/procurement_alert", 
    response_model=ProcurementAlertResponse, 
    responses=ERROR_RESPONSES,
    description="Endpoint to trigger procurement alert based on predicted demand. Used by Foundry AI agent to trigger when certain demand thresholds are met."
)             
def api_procurement_alert(body: ProcurementAlertRequest):
    result = procurement_alert(body.item_name, body.predicted_demand, body.justification)
    if isinstance(result, str):
        return success_response(message=result, data=result)
    return success_response(message="Procurement alert processed successfully", data=result)
