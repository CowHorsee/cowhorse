from pydantic import BaseModel

from api.schema.schema_base import BaseResponse


class UpdateInventoryRequest(BaseModel):
    csv_content: str


class CountInventoryResponse(BaseResponse):
    data: int | dict[str, int]


class UpdateInventoryResponse(BaseResponse):
    data: str
