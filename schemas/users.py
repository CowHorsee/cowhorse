from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    admin_id: str
    email: str
    name: str
    role_name: str
    password: str | None = None


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


class LoginResponse(BaseModel):
    role: str
    user_id: str
    email: str
    name: str
    message: str


class UserResponse(BaseModel):
    user_id: str
    name: str
    email: str
    role_id: str | int | None = None
    created_at: str | None = None
    role_name: str | None = None