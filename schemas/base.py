from typing import Any, Sequence

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class APIResponse(BaseModel):
    success: bool = True
    message: str = "Success"
    data: Any | None = None
    errors: list[str] | None = None


def success_response(data: Any | None = None, message: str = "Success") -> APIResponse:
    return APIResponse(success=True, message=message, data=data)


def error_response(message: str, errors: Sequence[str] | None = None) -> APIResponse:
    return APIResponse(
        success=False,
        message=message,
        errors=list(errors) if errors is not None else None,
    )