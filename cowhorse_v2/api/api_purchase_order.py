import logging
import json
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from scripts.purchase_order import create_po, get_po_ticket, get_po_details, update_po_status

router = APIRouter(prefix="/api/po", tags=["Purchase Order"])

import asyncio
from sharedlib.pdf_helper.pdf import generate_po_doc
from sharedlib.email_helper.email import quick_send
from sharedlib.db_helper.db_ops import DBHelper

@router.post("/create_po")
async def api_create_po(body: dict[str, Any]):
    try:
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
        
        if isinstance(result, (dict, list)):
            return JSONResponse(json.loads(json.dumps(result)), status_code=200 if result else 400)
        return PlainTextResponse(str(result), status_code=200 if result else 400)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.get("/get_po_ticket")
def api_get_po_ticket(user_id: str = Query(...)):
    try:
        result = get_po_ticket(user_id)
        if isinstance(result, str):
            return PlainTextResponse(result, status_code=400)
        return JSONResponse(json.loads(json.dumps(result)), status_code=200)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.get("/get_po_details")
def api_get_po_details(user_id: str = Query(...), po_id: str = Query(...)):
    try:
        result = get_po_details(user_id, po_id)
        if isinstance(result, str):
            return PlainTextResponse(result, status_code=400)
        return JSONResponse(json.loads(json.dumps(result)), status_code=200)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/update_po_status")
def api_update_po_status(body: dict[str, Any]):
    try:
        result = update_po_status(body.get('supplier_id'), body.get('po_id'), body.get('status_name'))
        status = 200 if result is True else 400
        return PlainTextResponse(str(result), status_code=status)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
