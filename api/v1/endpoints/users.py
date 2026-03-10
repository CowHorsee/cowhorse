from fastapi import APIRouter, HTTPException, Query

from schemas.users import (
    ChangePasswordRequest,
    ForgetPasswordRequest,
    LoginRequest,
    ModifyRoleRequest,
    RegisterRequest,
)
from services.user_management import (
    change_password,
    forget_password,
    list_users,
    login,
    modify_role,
    register,
    search_user,
)

router = APIRouter(prefix="/user", tags=["User Management"])


@router.post("/login")
def api_login(body: LoginRequest):
    try:
        role, user_id, msg = login(body.email, body.password)
        if "Successful" in msg:
            return {"role": role, "user_id": user_id, "message": msg}
        raise HTTPException(status_code=401, detail=msg)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/register")
def api_register(body: RegisterRequest):
    try:
        result = register(body.admin_id, body.email, body.name, body.role_name, body.password)
        if "Successful" in result:
            return result
        raise HTTPException(status_code=403, detail=result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/forget_password")
def api_forget_password(body: ForgetPasswordRequest):
    try:
        result = forget_password(body.user_id)
        if "Success" in result:
            return result
        raise HTTPException(status_code=400, detail=result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/modify_role")
def api_modify_role(body: ModifyRoleRequest):
    try:
        result = modify_role(body.admin_id, body.user_id, body.new_role_name)
        if "Success" in result:
            return result
        raise HTTPException(status_code=403, detail=result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/change_password")
def api_change_password(body: ChangePasswordRequest):
    try:
        result = change_password(body.user_id, body.old_password, body.new_password)
        if "Success" in result:
            return result
        raise HTTPException(status_code=401, detail=result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/list_users")
def api_list_users(admin_id: str = Query(...)):
    try:
        result = list_users(admin_id)
        if isinstance(result, str) and result.startswith("Error"):
            raise HTTPException(status_code=403, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/search_user")
def api_search_user(
    email: str | None = Query(default=None),
    name: str | None = Query(default=None),
    role_name: str | None = Query(default=None),
):
    try:
        return search_user(email, name, role_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc