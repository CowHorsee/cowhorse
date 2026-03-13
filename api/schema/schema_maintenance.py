from pydantic import BaseModel

from api.schema.schema_base import BaseResponse


class DataLoaderResponse(BaseModel):
    message: str
    details: dict[str, str]


class DataLoaderAPIResponse(BaseResponse):
    data: DataLoaderResponse
