from typing import Generic, Sequence, TypeVar

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str = "Success"
    data: T | None = None
    errors: list[str] | None = None


def success_response(data: T | None = None, message: str = "Success") -> APIResponse[T]:
    return APIResponse[T](success=True, message=message, data=data)


def error_response(message: str, errors: Sequence[str] | None = None) -> APIResponse[None]:
    return APIResponse[None](
        success=False,
        message=message,
        errors=list(errors) if errors is not None else None,
    )