import logging

from fastapi import APIRouter, HTTPException, Query

from db.table_storage import DBHelper
from integrations.email import quick_send
from integrations.pdf import generate_po_doc
from schemas.base import APIResponse, success_response
from schemas.purchase_orders import (
    CreatePORequest,
    PODetailsResponse,
    POTicketResponse,
    UpdatePOStatusRequest,
)
from services.purchase_orders import (
    create_po,
    get_po_details,
    get_po_ticket,
    update_po_status,
)

router = APIRouter(prefix="/po", tags=["Purchase Order"])


@router.post("/create_po", response_model=APIResponse)
async def api_create_po(body: CreatePORequest):
    try:
        result = create_po(body.pr_id, body.proc_item, body.user_id)

        if isinstance(result, list):
            db = DBHelper()
            officer_df = db.extract("user", conditions={"user_id": body.user_id})
            officer_email = officer_df.iloc[0]["email"] if not officer_df.empty else None

            roles = db.extract("dim_role", conditions={"role_name": "Procurement Manager"})
            manager_emails: list[str] = []
            if not roles.empty:
                manager_role_id = roles.iloc[0]["role_id"]
                managers = db.extract("user", conditions={"role_id": int(manager_role_id)})
                manager_emails = managers["email"].tolist() if not managers.empty else []

            for po_id in result:
                try:
                    pdf_path = await generate_po_doc(po_id)
                    po_header = db.extract("purchase_order", conditions={"po_id": po_id})
                    if not po_header.empty:
                        supplier_id = po_header.iloc[0]["supplier_id"]
                        supplier_df = db.extract("supplier", conditions={"supplier_id": supplier_id})
                        supplier_email = supplier_df.iloc[0]["email"] if not supplier_df.empty else None
                        if supplier_email:
                            quick_send(
                                template_type="PURCHASE_ORDER",
                                recipient_email=supplier_email,
                                subject=f"New Purchase Order: {po_id}",
                                cc_emails=manager_emails + ([officer_email] if officer_email else []),
                                attachments=[pdf_path] if pdf_path else None,
                                doc_id=po_id,
                                date=po_header.iloc[0]["created_at"][:10]
                                if po_header.iloc[0].get("created_at")
                                else None,
                            )
                except Exception as pdf_err:
                    logging.error(f"Failed to generate/send PO PDF/Email for {po_id}: {pdf_err}")

        if not result:
            raise HTTPException(status_code=400, detail="Validation failed")

        return success_response(data=result, message="Purchase orders created successfully")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/get_po_ticket", response_model=APIResponse)
def api_get_po_ticket(user_id: str = Query(...)):
    try:
        result = get_po_ticket(user_id)
        if isinstance(result, str) and result.startswith("Error"):
            raise HTTPException(status_code=400, detail=result)
        return success_response(data=result, message="Purchase orders retrieved successfully")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/get_po_details", response_model=APIResponse)
def api_get_po_details(user_id: str = Query(...), po_id: str = Query(...)):
    try:
        result = get_po_details(user_id, po_id)
        if isinstance(result, str) and result.startswith("Error"):
            raise HTTPException(status_code=400, detail=result)
        return success_response(data=result, message="Purchase order details retrieved successfully")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/update_po_status", response_model=APIResponse)
def api_update_po_status(body: UpdatePOStatusRequest):
    try:
        result = update_po_status(body.supplier_id, body.po_id, body.status_name)
        if result is True:
            return success_response(data=True, message="Purchase order status updated successfully")
        raise HTTPException(status_code=400, detail=str(result))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc