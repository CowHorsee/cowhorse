from pydantic import BaseModel

from api.schema.schema_base import BaseResponse


class UpdateInventoryRequest(BaseModel):
    csv_content: str


from typing import Any

class CountInventoryResponse(BaseResponse):
    data: list[dict[str, Any]]


class UpdateInventoryResponse(BaseResponse):
    data: str


class GraphDatapointResponse(BaseResponse):
    data: list[dict[str, Any]]
