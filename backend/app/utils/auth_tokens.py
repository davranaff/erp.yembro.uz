from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from typing import Any


class TokenError(ValueError):
    """Raised when a signed auth token is invalid."""


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sign(message: bytes, secret_key: str) -> str:
    digest = hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(digest)


def create_signed_token(
    *,
    subject: str,
    token_type: str,
    secret_key: str,
    expires_in: timedelta,
) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + expires_in
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": token_urlsafe(16),
    }

    header_segment = _b64url_encode(_json_bytes(header))
    payload_segment = _b64url_encode(_json_bytes(payload))
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature_segment = _sign(signing_input, secret_key)
    return f"{header_segment}.{payload_segment}.{signature_segment}", expires_at


def decode_signed_token(
    token: str,
    *,
    secret_key: str,
    expected_type: str | None = None,
) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("Invalid token format")

    header_segment, payload_segment, signature_segment = parts
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    expected_signature = _sign(signing_input, secret_key)

    if not hmac.compare_digest(signature_segment, expected_signature):
        raise TokenError("Invalid token signature")

    try:
        payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise TokenError("Invalid token payload") from exc

    if not isinstance(payload, dict):
        raise TokenError("Invalid token payload")

    if expected_type and payload.get("type") != expected_type:
        raise TokenError("Invalid token type")

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise TokenError("Invalid token subject")

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise TokenError("Invalid token expiry")
    if int(datetime.now(timezone.utc).timestamp()) >= exp:
        raise TokenError("Token expired")

    return payload


def extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None

    cleaned = authorization.strip()
    if not cleaned:
        return None

    scheme, separator, value = cleaned.partition(" ")
    if separator and scheme.lower() == "bearer":
        token = value.strip()
        return token or None

    return None
