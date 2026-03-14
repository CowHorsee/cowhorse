from pydantic import BaseModel, Field

from api.schema.schema_base import BaseResponse


class CreatePRRequest(BaseModel):
    user_id: str
    proc_item: list[dict[str, int]] = Field(..., description="List of dictionaries representing item name and quantity.")
    justification: str


class AcceptPRSuggestionRequest(BaseModel):
    pr_id: str
    officer_id: str


class ModifyPRRequest(BaseModel):
    user_id: str
    pr_id: str
    proc_item: list[dict[str, int]] = Field(..., description="List of dictionaries representing item name and quantity.")
    justification: str


class ReviewPRRequest(BaseModel):
    pr_id: str
    decision: str = Field(..., description="Decision made by the manager. Accepts 'approve', 'approved', 'accept', or 'accepted' to approve. Any other value will reject the PR.")
    manager_id: str


class ProcurementAlertRequest(BaseModel):
    item_name: str
    predicted_demand: float
    justification: str


class PRBridgeItemResponse(BaseModel):
    doc_id: str
    item_id: str | int
    quantity: int | float


class PRTicketResponse(BaseModel):
    pr_id: str
    status_id: str | int
    created_at: str | None = None
    created_by: str | None = None
    last_modified_at: str | None = None
    last_modified_by: str | None = None
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    justification: str | None = None
    status_name: str | None = None
    creator_role: str | None = None


class CreatePRResponse(BaseModel):
    pr_id: str
    status: int
    items: list[PRBridgeItemResponse]


class PRDetailHeaderResponse(BaseModel):
    pr_id: str
    status_id: str | int
    created_at: str | None = None
    created_by: str | None = None
    last_modified_at: str | None = None
    last_modified_by: str | None = None
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    justification: str | None = None
    status_name: str | None = None
    creator_role: str | None = None
    user_id: str | None = None


class PRDetailItemResponse(BaseModel):
    item_id: str | int
    quantity: int | float | None = None
    doc_id: str | None = None


class PRDetailsResponse(BaseModel):
    header: PRDetailHeaderResponse
    items: list[PRDetailItemResponse]


class DataLoaderResponse(BaseModel):
    message: str
    details: dict[str, str]


class CreatePRAPIResponse(BaseResponse):
    data: CreatePRResponse


class AcceptPRSuggestionResponse(BaseResponse):
    data: str


class ModifyPRResponse(BaseResponse):
    data: str


class PRTicketListResponse(BaseResponse):
    data: list[PRTicketResponse]


class PRDetailsAPIResponse(BaseResponse):
    data: PRDetailsResponse


class ReviewPRResponse(BaseResponse):
    data: str


class ProcurementAlertResponse(BaseResponse):
    data: CreatePRResponse | str


class DataLoaderAPIResponse(BaseResponse):
    data: DataLoaderResponse
