from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Union

# --- User Management Schemas ---

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    role: str
    user_id: str
    message: str

class RegisterRequest(BaseModel):
    admin_id: str
    email: EmailStr
    name: str
    role_name: str
    password: Optional[str] = None

class ForgetPasswordRequest(BaseModel):
    user_id: str

class ModifyRoleRequest(BaseModel):
    admin_id: str
    user_id: str
    new_role_name: str

class ChangePasswordRequest(BaseModel):
    user_id: str
    old_password: str
    new_password: str

class UserSearchResponse(BaseModel):
    user_id: str
    name: str
    email: str
    role_name: str

# --- Purchase Request Schemas ---

class PRCreateRequest(BaseModel):
    user_id: str
    proc_item: Dict[str, int]
    justification: str

class PRCreateResponse(BaseModel):
    pr_id: str
    status: int
    items: List[dict]

class PRAcceptSuggestionRequest(BaseModel):
    pr_id: str
    officer_id: str

class PRModifyRequest(BaseModel):
    user_id: str
    pr_id: str
    proc_item: Dict[str, int]
    justification: str

class PRTicketResponse(BaseModel):
    # This might vary based on actual DB output, but here's a general structure
    pr_id: str
    status_name: str
    created_at: str
    # Add other fields as discovered

class PRReviewRequest(BaseModel):
    pr_id: str
    decision: str = Field(..., pattern="^(approve|reject)$")
    manager_id: str

class ProcurementAlertRequest(BaseModel):
    item_name: str
    predicted_demand: float
    justification: str

# --- Purchase Order Schemas ---

class POCreateRequest(BaseModel):
    pr_id: str
    proc_item: List[Dict[str, Union[str, int]]]
    user_id: str

class POUpdateRequest(BaseModel):
    supplier_id: str
    po_id: str
    status_name: str = Field(..., pattern="^(Awaiting Warehouse|Shipped|Delivered)$")

# --- Warehouse Schemas ---

class InventoryUpdateRequest(BaseModel):
    incoming_csv_path: str
