from pydantic import BaseModel, ConfigDict

from api.schemas.base import BaseResponse


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


class UserResponse(BaseModel):
    user_id: str
    name: str
    email: str
    role_id: str | int | None = None
    created_at: str | None = None
    role_name: str | None = None


class LoginAPIResponse(BaseResponse):
    data: LoginResponse


class RegisterUserResponse(BaseResponse):
    data: str


class ForgetPasswordResponse(BaseResponse):
    data: str


class ModifyRoleResponse(BaseResponse):
    data: str


class ChangePasswordResponse(BaseResponse):
    data: str


class ListUsersResponse(BaseResponse):
    data: list[UserResponse]


class SearchUsersResponse(BaseResponse):
    data: list[UserResponse]