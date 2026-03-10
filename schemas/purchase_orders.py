from pydantic import BaseModel


class CreatePORequest(BaseModel):
    pr_id: str
    proc_item: list[dict[str, int]]
    user_id: str


class UpdatePOStatusRequest(BaseModel):
    supplier_id: str
    po_id: str
    status_name: str
