from pydantic import BaseModel


class CreatePRRequest(BaseModel):
    user_id: str
    proc_item: dict[str, int]
    justification: str


class AcceptPRSuggestionRequest(BaseModel):
    pr_id: str
    officer_id: str


class ModifyPRRequest(BaseModel):
    user_id: str
    pr_id: str
    proc_item: dict[str, int]
    justification: str


class ReviewPRRequest(BaseModel):
    pr_id: str
    decision: str
    manager_id: str


class ProcurementAlertRequest(BaseModel):
    item_name: str
    predicted_demand: float
    justification: str
