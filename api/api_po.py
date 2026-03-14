import logging

from fastapi import APIRouter, HTTPException, Query

from api.schema.schema_base import ERROR_RESPONSES, success_response
from api.schema.schema_po import (
    CreatePORequest,
    CreatePOResponse,
    PODetailsAPIResponse,
    POTicketListResponse,
    UpdatePOStatusRequest,
    UpdatePOStatusResponse,
)
from services.po import create_po, get_po_details, get_po_ticket, update_po_status
from services.sharedlib.db_helper.db_helper import DBHelper
from services.sharedlib.email_helper.email_helper import quick_send
from services.sharedlib.pdf_helper.pdf_helper import generate_po_doc

router = APIRouter(prefix="/po", tags=["Purchase Order"])


@router.post("/create_po", response_model=CreatePOResponse, responses=ERROR_RESPONSES)
async def api_create_po(body: CreatePORequest):
    result = create_po(body.pr_id, body.proc_item, body.user_id)

    if isinstance(result, list):
        db = DBHelper()
        officer_df = db.extract("user", conditions={"user_id": body.user_id})
        officer_email = officer_df.iloc[0]["email"] if not officer_df.empty else None

        pr_header_df = db.extract("purchase_request", conditions={"pr_id": body.pr_id})
        reviewer_id = pr_header_df.iloc[0].get("reviewed_by") if not pr_header_df.empty else None
        manager_email = None
        if reviewer_id:
            reviewer_df = db.extract("user", conditions={"user_id": reviewer_id})
            manager_email = reviewer_df.iloc[0]["email"] if not reviewer_df.empty else None

        for po_id in result:
            try:
                pdf_path = await generate_po_doc(po_id)
                po_header = db.extract("purchase_order", conditions={"po_id": po_id})
                if not po_header.empty:
                    supplier_id = po_header.iloc[0]["supplier_id"]
                    supplier_df = db.extract("supplier", conditions={"supplier_id": supplier_id})
                    supplier_email = supplier_df.iloc[0]["email"] if not supplier_df.empty else None
                    if supplier_email:
                        cc_list = []
                        if manager_email:
                            cc_list.append(manager_email)
                        if officer_email:
                            cc_list.append(officer_email)
                        
                        quick_send(
                            template_type="PURCHASE_ORDER",
                            recipient_email=supplier_email,
                            subject=f"New Purchase Order: {po_id}",
                            cc_emails=cc_list if cc_list else None,
                            attachments=[pdf_path] if pdf_path else None,
                            doc_id=po_id,
                            date=po_header.iloc[0]["created_at"][:10]
                            if po_header.iloc[0].get("created_at")
                            else None,
                        )
            except Exception as pdf_err:
                logging.error(f"Failed to generate/send PO PDF/Email for {po_id}: {pdf_err}")

    return success_response(message="Purchase orders created successfully", data=result)


@router.get("/get_po_ticket", response_model=POTicketListResponse, responses=ERROR_RESPONSES)
def api_get_po_ticket(user_id: str = Query(...)):
    result = get_po_ticket(user_id)
    return success_response(message="Purchase orders retrieved successfully", data=result)


@router.get("/get_po_details", response_model=PODetailsAPIResponse, responses=ERROR_RESPONSES)
def api_get_po_details(user_id: str = Query(...), po_id: str = Query(...)):
    result = get_po_details(user_id, po_id)
    return success_response(message="Purchase order details retrieved successfully", data=result)


@router.post(
    "/update_po_status", 
    response_model=UpdatePOStatusResponse, 
    responses=ERROR_RESPONSES,
    description="Updates the status of a PO. The status_name field must exactly match an entry in the dim_status table (e.g., 'Pending Delivery', 'Delivered')."
)
def api_update_po_status(body: UpdatePOStatusRequest):
    update_po_status(body.supplier_id, body.po_id, body.status_name)
    return success_response(message="Purchase order status updated successfully", data=True)
