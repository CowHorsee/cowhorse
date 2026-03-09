import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from scripts.user_management import (
    change_password,
    forget_password,
    login,
    modify_role,
    register,
    search_user,
)

router = APIRouter(prefix="/api/user", tags=["User Management"])


@router.post("/login")
def api_login(body: dict[str, Any]):
    try:
        email = body.get("email")
        password = body.get("password")
        role, user_id, msg = login(email, password)
        if "Successful" in msg:
            return JSONResponse({"role": role, "user_id": user_id, "message": msg}, status_code=200)
        return PlainTextResponse(msg, status_code=401)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/register")
def api_register(body: dict[str, Any]):
    try:
        result = register(
            body.get("admin_id"),
            body.get("email"),
            body.get("name"),
            body.get("role_name"),
            body.get("password"),
        )
        status = 200 if "Successful" in result else 403
        return PlainTextResponse(result, status_code=status)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/forget_password")
def api_forget_password(body: dict[str, Any]):
    try:
        result = forget_password(body.get("user_id"))
        return PlainTextResponse(result, status_code=200 if "Success" in result else 400)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/modify_role")
def api_modify_role(body: dict[str, Any]):
    try:
        result = modify_role(body.get("admin_id"), body.get("user_id"), body.get("new_role_name"))
        return PlainTextResponse(result, status_code=200 if "Success" in result else 403)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/change_password")
def api_change_password(body: dict[str, Any]):
    try:
        result = change_password(body.get("user_id"), body.get("old_password"), body.get("new_password"))
        return PlainTextResponse(result, status_code=200 if "Success" in result else 401)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/search_user")
def api_search_user(
    email: str | None = Query(default=None),
    name: str | None = Query(default=None),
    role_name: str | None = Query(default=None),
):
    try:
        result = search_user(email, name, role_name)
        return JSONResponse(json.loads(json.dumps(result)), status_code=200)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
