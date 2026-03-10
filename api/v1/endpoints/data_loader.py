from fastapi import APIRouter, HTTPException

from schemas.base import APIResponse, success_response
from schemas.purchase_requests import DataLoaderResponse
from services.data_loader import run_data_loader

router = APIRouter(prefix="/data-loader", tags=["Maintenance"])


@router.post("/run", response_model=APIResponse[DataLoaderResponse])
def api_run_data_loader():
    try:
        return success_response(data=run_data_loader(), message="Data loader completed successfully")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc