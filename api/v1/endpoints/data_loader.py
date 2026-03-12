from fastapi import APIRouter, HTTPException

from api.schemas.base import ERROR_RESPONSES, success_response
from api.schemas.purchase_requests import DataLoaderAPIResponse
from services.scripts.data_loader import run_data_loader

router = APIRouter(prefix="/data-loader", tags=["Maintenance"])


@router.post("/run", response_model=DataLoaderAPIResponse, responses=ERROR_RESPONSES)
def api_run_data_loader():
    try:
        return success_response(message="Data loader completed successfully", data=run_data_loader())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc