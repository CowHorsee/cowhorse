from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaseResponse(BaseModel):
    status: str = Field(default="success")
    message: str = Field(default="Success")


class ErrorResponse(BaseModel):
    error: str = Field(...)
    message: str = Field(...)
    details: Any | None = Field(default=None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "BadRequest",
                "message": "Validation failed",
                "details": ["body -> email: Field required"],
            }
        }
    )


def success_response(message: str = "Success", data: Any | None = None) -> dict[str, Any]:
    response = {
        "status": "success",
        "message": message,
    }
    if data is not None:
        response["data"] = data
    return response


def error_response(
    message: str,
    details: Any | None = None,
    error: str = "RequestError",
) -> ErrorResponse:
    return ErrorResponse(error=error, message=message, details=details)


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Bad Request"},
    401: {"model": ErrorResponse, "description": "Unauthorized"},
    403: {"model": ErrorResponse, "description": "Forbidden"},
    422: {"model": ErrorResponse, "description": "Validation Error"},
    500: {"model": ErrorResponse, "description": "Internal Server Error"},
}