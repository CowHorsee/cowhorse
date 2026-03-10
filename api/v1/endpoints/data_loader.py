from fastapi import APIRouter, HTTPException

from services.data_loader import run_data_loader

router = APIRouter(prefix="/data-loader", tags=["Maintenance"])


@router.post("/run")
def api_run_data_loader():
    try:
        return run_data_loader()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
