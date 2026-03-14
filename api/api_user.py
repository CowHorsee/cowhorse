from fastapi import APIRouter, HTTPException, Query

from api.schema.schema_base import ERROR_RESPONSES, success_response
from api.schema.schema_user import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    ForgetPasswordRequest,
    ForgetPasswordResponse,
    ListUsersResponse,
    LoginAPIResponse,
    LoginRequest,
    ModifyRoleRequest,
    ModifyRoleResponse,
    RegisterRequest,
    RegisterUserResponse,
    SearchUsersResponse,
)
from services.user import (
    change_password,
    forget_password,
    list_users,
    login,
    modify_role,
    register,
    search_user,
)

router = APIRouter(prefix="/user", tags=["User Management"])


@router.post("/login", response_model=LoginAPIResponse, responses=ERROR_RESPONSES)
def api_login(body: LoginRequest):
    role, user_id, email, name, msg = login(body.email, body.password)
    return success_response(
        message=msg,
        data={
            "role": role,
            "user_id": user_id,
            "email": email,
            "name": name,
            "message": msg,
        },
    )


@router.post(
    "/register", 
    response_model=RegisterUserResponse, 
    responses=ERROR_RESPONSES,
    description="Registers a new user. The role_name field must exactly match an existing role in the database (e.g., 'Procurement Officer', 'Procurement Manager', 'Supplier', 'Warehouse Personnel', 'Admin')."
)
def api_register(body: RegisterRequest):
    result = register(body.admin_id, body.email, body.name, body.role_name, body.password)
    return success_response(message=result, data=result)


@router.post("/forget_password", response_model=ForgetPasswordResponse, responses=ERROR_RESPONSES)
def api_forget_password(body: ForgetPasswordRequest):
    result = forget_password(body.user_id)
    return success_response(message=result, data=result)


@router.post(
    "/modify_role", 
    response_model=ModifyRoleResponse, 
    responses=ERROR_RESPONSES,
    description="Modifies a user's role. The new_role_name field must exactly match an existing role (e.g., 'Procurement Officer', 'Procurement Manager', 'Supplier', 'Warehouse Personnel', 'Admin')."
)
def api_modify_role(body: ModifyRoleRequest):
    result = modify_role(body.admin_id, body.user_id, body.new_role_name)
    return success_response(message=result, data=result)


@router.post("/change_password", response_model=ChangePasswordResponse, responses=ERROR_RESPONSES)
def api_change_password(body: ChangePasswordRequest):
    result = change_password(body.user_id, body.old_password, body.new_password)
    return success_response(message=result, data=result)


@router.get("/list_users", response_model=ListUsersResponse, responses=ERROR_RESPONSES)
def api_list_users(admin_id: str = Query(...)):
    result = list_users(admin_id)
    return success_response(message="Users retrieved successfully", data=result)


@router.get("/search_user", response_model=SearchUsersResponse, responses=ERROR_RESPONSES)
def api_search_user(
    email: str | None = Query(default=None),
    name: str | None = Query(default=None),
    role_name: str | None = Query(default=None),
):
    return success_response(
        message="Users retrieved successfully",
        data=search_user(email, name, role_name),
    )
