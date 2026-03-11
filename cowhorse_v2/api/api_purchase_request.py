import logging
import json
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from scripts.purchase_request import (
    create_pr, accept_pr_suggestion, modify_pr, 
    get_pr_ticket, get_pr_details, review_pr, procurement_alert
)

router = APIRouter(prefix="/api/pr", tags=["Purchase Request"])

import asyncio
from sharedlib.pdf_helper.pdf import generate_pr_doc
from sharedlib.email_helper.email_helper import quick_send
from sharedlib.db_helper.db_ops import DBHelper

@router.post("/create_pr")
async def api_create_pr(body: dict[str, Any]):
    try:
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

        return JSONResponse(json.loads(json.dumps(result)), status_code=200)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/accept_pr_suggestion")
def api_accept_pr_suggestion(body: dict[str, Any]):
    try:
        result = accept_pr_suggestion(body.get('pr_id'), body.get('officer_id'))
        return PlainTextResponse(result, status_code=200 if "Success" in result else 400)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/modify_pr")
def api_modify_pr(body: dict[str, Any]):
    try:
        result = modify_pr(body.get('user_id'), body.get('pr_id'), body.get('proc_item'), body.get('justification'))
        return PlainTextResponse(result, status_code=200 if "Success" in result else 400)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.get("/get_pr_ticket")
def api_get_pr_ticket(
    user_id: str = Query(...),
    pr_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    try:
        result = get_pr_ticket(user_id, pr_id, status)
        return JSONResponse(json.loads(json.dumps(result)), status_code=200)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.get("/get_pr_details")
def api_get_pr_details(user_id: str = Query(...), pr_id: str = Query(...)):
    try:
        result = get_pr_details(user_id, pr_id)
        return JSONResponse(json.loads(json.dumps(result)), status_code=200)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/review_pr")
def api_review_pr(body: dict[str, Any]):
    try:
        result = review_pr(body.get('pr_id'), body.get('decision'), body.get('manager_id'))
        status = 200 if "Success" in result or " PR " in result else 400
        return PlainTextResponse(result, status_code=status)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/procurement_alert")
def api_procurement_alert(body: dict[str, Any]):
    try:
        result = procurement_alert(body.get('item_name'), body.get('predicted_demand'), body.get('justification'))
        if isinstance(result, dict):
            return JSONResponse(json.loads(json.dumps(result)), status_code=200)
        return PlainTextResponse(result, status_code=200)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
