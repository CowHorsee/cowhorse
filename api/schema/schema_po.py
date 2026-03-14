from pydantic import BaseModel

from api.schema.schema_base import BaseResponse


class CreatePORequest(BaseModel):
    pr_id: str
    proc_item: list[dict[str, int]]
    user_id: str


class UpdatePOStatusRequest(BaseModel):
    supplier_id: str
    po_id: str
    status_name: str


class UserContact(BaseModel):
    name: str | None = None
    email: str | None = None


class POTicketResponse(BaseModel):
    po_id: str
    pr_id: str | None = None
    status: str | int
    status_name: str | None = None
    created_at: str | None = None
    creator_role: str | None = None


class POItemResponse(BaseModel):
    item_id: str | int
    item_name: str | None = None
    quantity: int | float | None = None
    unit_price: int | float | None = None


class PODetailsResponse(BaseModel):
    po_id: str
    pr_id: str | None = None
    status: str | int
    supplier_id: str | int
    created_at: str | None = None
    created_by: str | None = None
    status_id: str | None = None
    status_name: str | None = None
    creator_role: str | None = None
    supplier: UserContact | None = None
    officer: UserContact | None = None
    manager: UserContact | None = None
    items: list[POItemResponse]


class CreatePOResponse(BaseResponse):
    data: list[str]


class POTicketListResponse(BaseResponse):
    data: list[POTicketResponse]


class PODetailsAPIResponse(BaseResponse):
    data: PODetailsResponse


class UpdatePOStatusResponse(BaseResponse):
    data: bool
