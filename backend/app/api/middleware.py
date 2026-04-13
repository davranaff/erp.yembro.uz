from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response


class ApiResponseMiddleware(BaseHTTPMiddleware):
    """Return all API JSON responses in unified envelope."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path.startswith(("/openapi", "/docs", "/redoc", "/favicon")):
            return await call_next(request)

        response = await call_next(request)

        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return response

        parsed = await self._extract_json(response)
        if parsed is None:
            return response

        headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower() not in {"content-length", "content-type"}
        }

        if (
            isinstance(parsed, dict)
            and "ok" in parsed
            and "data" in parsed
            and "error" in parsed
        ):
            return JSONResponse(content=parsed, status_code=response.status_code, headers=headers)

        if response.status_code < 400:
            wrapped: dict[str, Any] = {
                "ok": True,
                "data": parsed,
                "error": None,
            }
        else:
            error = self._normalize_error_payload(parsed)
            wrapped = {
                "ok": False,
                "data": None,
                "error": error,
            }

        return JSONResponse(content=wrapped, status_code=response.status_code, headers=headers)

    @staticmethod
    async def _extract_json(response: Response) -> dict[str, Any] | list[dict[str, Any]] | Any | None:
        raw_body = getattr(response, "body", None)
        if raw_body is None:
            body_parts: list[bytes] = []
            body_iterator = getattr(response, "body_iterator", None)
            if body_iterator is None:
                return None
            async for chunk in body_iterator:
                if chunk:
                    body_parts.append(chunk)
            if not body_parts:
                return None
            raw_body = b"".join(body_parts)
        elif isinstance(raw_body, str):
            raw_body = raw_body.encode()

        if not raw_body:
            return None

        try:
            return json.loads(raw_body.decode())
        except Exception:
            return None

    @staticmethod
    def _normalize_error_payload(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            if isinstance(payload.get("error"), dict):
                normalized = payload.get("error")
                if normalized is not None:
                    return {
                        "code": normalized.get("code", "api_error"),
                        "message": normalized.get("message", "Request failed"),
                        "details": normalized.get("details", None),
                    }
            if "code" in payload and "message" in payload:
                return {
                    "code": payload.get("code", "api_error"),
                    "message": payload.get("message", "Request failed"),
                    "details": payload.get("details", None),
                }
            return {
                "code": "api_error",
                "message": payload.get("detail", "Request failed"),
                "details": payload,
            }
        return {"code": "api_error", "message": str(payload), "details": None}
