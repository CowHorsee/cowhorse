import logging
import json
import azure.functions as func
from azure_functions_openapi.decorator import openapi
from scripts.user_management import login, register, forget_password, modify_role, change_password, search_user

bp = func.Blueprint(name='user_v2', url_prefix='/user')

@bp.route(route="login", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Login user",
    description="Authenticates a user by email and password. Returns the user's role and unique ID upon successful authentication.",
    tags=["User Management"],
    route="/api/user/login",
    method="POST",
    request_body={"type": "object", "required": ["email", "password"], "properties": {
        "email": {"type": "string", "format": "email", "description": "User's registered email address"},
        "password": {"type": "string", "format": "password", "description": "User's password"}
    }},
    response={
        200: {
            "description": "Login successful",
            "content": {"application/json": {"schema": {"type": "object", "properties": {
                "role": {"type": "string", "example": "Procurement Manager"},
                "user_id": {"type": "string", "format": "uuid"},
                "message": {"type": "string", "example": "Login Successful"}
            }}}}
        },
        401: {"description": "Invalid credentials provided"}
    }
)
def api_login(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        email, password = body.get('email'), body.get('password')
        role, user_id, msg = login(email, password)
        if "Successful" in msg:
            return func.HttpResponse(json.dumps({"role": role, "user_id": user_id, "message": msg}), status_code=200, mimetype="application/json")
        return func.HttpResponse(msg, status_code=401)
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="register", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Register user",
    description="Creates a new user profile in the system. Requires an admin user's ID for authorization.",
    tags=["User Management"],
    route="/api/user/register",
    method="POST",
    request_body={"type": "object", "required": ["admin_id", "email", "name", "role_name"], "properties": {
        "admin_id": {"type": "string", "format": "uuid", "description": "ID of the administrator performing the registration"},
        "email": {"type": "string", "format": "email", "description": "New user's email address"},
        "name": {"type": "string", "description": "Full name of the new user"},
        "role_name": {"type": "string", "enum": ["Procurement Officer", "Procurement Manager", "Warehouse Personnel", "Supplier", "Admin"], "description": "Assigned role"},
        "password": {"type": "string", "description": "Optional initial password. If omitted, a random one will be generated and emailed."}
    }},
    response={
        200: {"description": "User registered successfully"},
        403: {"description": "Permission denied: admin_id not authorized to create users"},
        400: {"description": "Invalid input or email already registered"}
    }
)
def api_register(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        result = register(body.get('admin_id'), body.get('email'), body.get('name'), body.get('role_name'), body.get('password'))
        status = 200 if "Successful" in result else 403
        return func.HttpResponse(result, status_code=status)
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="forget_password", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Reset user password",
    description="Initiates a password reset for the specified user. Generates a new temporary password and sends it via email.",
    tags=["User Management"],
    route="/api/user/forget_password",
    method="POST",
    request_body={"type": "object", "required": ["user_id"], "properties": {
        "user_id": {"type": "string", "format": "uuid", "description": "Unique ID of the user requiring a reset"}
    }},
    response={
        200: {"description": "Temporary password generated and email notification triggered"},
        400: {"description": "User not found or operation failed"}
    }
)
def api_forget_password(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        result = forget_password(body.get('user_id'))
        return func.HttpResponse(result, status_code=200 if "Success" in result else 400)
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="modify_role", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Modify user role",
    description="Updates the role of an existing user. Requires authorized administrator credentials.",
    tags=["User Management"],
    route="/api/user/modify_role",
    method="POST",
    request_body={"type": "object", "required": ["admin_id", "user_id", "new_role_name"], "properties": {
        "admin_id": {"type": "string", "format": "uuid", "description": "ID of the administrator performing the update"},
        "user_id": {"type": "string", "format": "uuid", "description": "ID of the target user"},
        "new_role_name": {"type": "string", "enum": ["Procurement Officer", "Procurement Manager", "Warehouse Personnel", "Supplier", "Admin"], "description": "New role to assign"}
    }},
    response={
        200: {"description": "User role updated successfully"},
        403: {"description": "Authorization failed for admin_id"},
        400: {"description": "Invalid user_id or role name"}
    }
)
def api_modify_role(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        result = modify_role(body.get('admin_id'), body.get('user_id'), body.get('new_role_name'))
        return func.HttpResponse(result, status_code=200 if "Success" in result else 403)
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="change_password", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Change user password",
    description="Allows a user to self-update their password by providing their current credentials.",
    tags=["User Management"],
    route="/api/user/change_password",
    method="POST",
    request_body={"type": "object", "required": ["user_id", "old_password", "new_password"], "properties": {
        "user_id": {"type": "string", "format": "uuid", "description": "ID of the user changing the password"},
        "old_password": {"type": "string", "description": "Current password for verification"},
        "new_password": {"type": "string", "description": "New password to set"}
    }},
    response={
        200: {"description": "Password updated successfully"},
        401: {"description": "Incorrect old password"},
        400: {"description": "User not found"}
    }
)
def api_change_password(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        result = change_password(body.get('user_id'), body.get('old_password'), body.get('new_password'))
        return func.HttpResponse(result, status_code=200 if "Success" in result else 401)
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)

@bp.route(route="search_user", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@openapi(
    summary="Search users",
    description="Retrieves user profiles based on optional filters like email, name, or role. Join with dim_role is performed internally.",
    tags=["User Management"],
    route="/api/user/search_user",
    method="GET",
    parameters=[
        {"name": "email", "in": "query", "type": "string", "description": "Filter by exact email match"},
        {"name": "name", "in": "query", "type": "string", "description": "Partial match on user's name"},
        {"name": "role_name", "in": "query", "type": "string", "description": "Filter by role name (e.g., Supplier)"}
    ],
    response={
        200: {
            "description": "Matching users retrieved",
            "content": {"application/json": {"schema": {"type": "array", "items": {"type": "object", "properties": {
                "user_id": {"type": "string"},
                "name": {"type": "string"},
                "email": {"type": "string"},
                "role_name": {"type": "string"}
            }}}}}
        }
    }
)
def api_search_user(req: func.HttpRequest) -> func.HttpResponse:
    try:
        email = req.params.get('email')
        name = req.params.get('name')
        role_name = req.params.get('role_name')
        result = search_user(email, name, role_name)
        return func.HttpResponse(json.dumps(result), status_code=200, mimetype="application/json")
    except Exception as e:
        return func.HttpResponse(str(e), status_code=500)
