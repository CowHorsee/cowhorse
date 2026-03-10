import logging

from fastapi import APIRouter, HTTPException, Query

from db.table_storage import DBHelper
from integrations.email import quick_send
from integrations.pdf import generate_pr_doc
from schemas.purchase_requests import (
    AcceptPRSuggestionRequest,
    CreatePRRequest,
    ModifyPRRequest,
    ProcurementAlertRequest,
    ReviewPRRequest,
)
from services.purchase_requests import (
    accept_pr_suggestion,
    create_pr,
    get_pr_details,
    get_pr_ticket,
    modify_pr,
    procurement_alert,
    review_pr,
)

router = APIRouter(prefix="/pr", tags=["Purchase Request"])


@router.post("/create_pr")
async def api_create_pr(body: CreatePRRequest):
    try:
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
                        item_count = sum(body.proc_item.values())
                        quick_send(
                            template_type="PURCHASE_REQUEST",
                            recipient_email=manager_emails[0],
                            subject=f"Action Required: New Purchase Request {pr_id}",
                            cc_emails=manager_emails[1:] + ([officer_email] if officer_email else []),
                            attachments=[pdf_path] if pdf_path else None,
                            doc_id=pr_id,
                            officer_name=officer_name,
                            item_count=item_count,
                        )
            except Exception as pdf_err:
                logging.error(f"Failed to generate/send PR PDF/Email: {pdf_err}")

        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/accept_pr_suggestion")
def api_accept_pr_suggestion(body: AcceptPRSuggestionRequest):
    try:
        result = accept_pr_suggestion(body.pr_id, body.officer_id)
        if "Success" in result:
            return result
        raise HTTPException(status_code=400, detail=result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/modify_pr")
def api_modify_pr(body: ModifyPRRequest):
    try:
        result = modify_pr(body.user_id, body.pr_id, body.proc_item, body.justification)
        if "updated" in result or "Success" in result:
            return result
        raise HTTPException(status_code=400, detail=result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/get_pr_ticket")
def api_get_pr_ticket(
    user_id: str = Query(...),
    pr_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    try:
        return get_pr_ticket(user_id, pr_id, status)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/get_pr_details")
def api_get_pr_details(user_id: str = Query(...), pr_id: str = Query(...)):
    try:
        result = get_pr_details(user_id, pr_id)
        if isinstance(result, str) and result.startswith("Error"):
            raise HTTPException(status_code=403, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/review_pr")
def api_review_pr(body: ReviewPRRequest):
    try:
        result = review_pr(body.pr_id, body.decision, body.manager_id)
        if result.startswith("Error"):
            raise HTTPException(status_code=400, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/procurement_alert")
def api_procurement_alert(body: ProcurementAlertRequest):
    try:
        return procurement_alert(body.item_name, body.predicted_demand, body.justification)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
