import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response


logger = logging.getLogger("cowhorse.http")

MAX_LOG_BODY_LENGTH = 4000
REDACTED = "***REDACTED***"
SENSITIVE_KEYS = {
    "access_token",
    "authorization",
    "api_key",
    "client_secret",
    "password",
    "password_hash",
    "refresh_token",
    "secret",
    "smtp_password",
    "token",
}


def _truncate(value: str) -> str:
    if len(value) <= MAX_LOG_BODY_LENGTH:
        return value
    return f"{value[:MAX_LOG_BODY_LENGTH]}... [truncated]"


def _redact_sensitive(data: Any) -> Any:
    if isinstance(data, dict):
        redacted: dict[str, Any] = {}
        for key, value in data.items():
            if key.lower() in SENSITIVE_KEYS:
                redacted[key] = REDACTED
            else:
                redacted[key] = _redact_sensitive(value)
        return redacted

    if isinstance(data, list):
        return [_redact_sensitive(item) for item in data]

    return data


def _decode_body(body: bytes, content_type: str | None) -> str:
    if not body:
        return ""

    normalized_content_type = (content_type or "").lower()
    if "multipart/form-data" in normalized_content_type:
        return "[multipart form data omitted]"
    if "application/octet-stream" in normalized_content_type:
        return "[binary payload omitted]"

    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return "[non-utf8 payload omitted]"

    if "application/json" in normalized_content_type:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return _truncate(text)
        return _truncate(json.dumps(_redact_sensitive(parsed), ensure_ascii=True))

    return _truncate(text)


async def log_http_payloads(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_body = await request.body()
    request_payload = _decode_body(request_body, request.headers.get("content-type"))

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": request_body, "more_body": False}

    request = Request(request.scope, receive)

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "HTTP %s %s failed request_payload=%s",
            request.method,
            request.url.path,
            request_payload or "[empty]",
        )
        raise

    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk

    response_payload = _decode_body(response_body, response.headers.get("content-type"))
    logger.info(
        "HTTP %s %s completed with status=%s request_payload=%s response_payload=%s",
        request.method,
        request.url.path,
        response.status_code,
        request_payload or "[empty]",
        response_payload or "[empty]",
    )

    return Response(
        content=response_body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
        background=response.background,
    )