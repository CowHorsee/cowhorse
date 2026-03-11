from pydantic import BaseModel

from api.schemas.base import BaseResponse


class UpdateInventoryRequest(BaseModel):
    incoming_csv_path: str


class CountInventoryResponse(BaseResponse):
    data: int | dict[str, int]


class UpdateInventoryResponse(BaseResponse):
    data: str