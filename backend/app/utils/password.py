from __future__ import annotations

import base64
import hashlib
import hmac
from secrets import token_bytes

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 200_000
_SALT_SIZE = 16
_KEY_SIZE = 32
_PREFIX = f"{_ALGORITHM}$"


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def hash_password(password: str) -> str:
    salt = token_bytes(_SALT_SIZE)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _ITERATIONS,
        dklen=_KEY_SIZE,
    )
    return f"{_ALGORITHM}${_ITERATIONS}${_b64encode(salt)}${_b64encode(derived)}"


def is_hashed_password(value: str) -> bool:
    if not isinstance(value, str):
        return False
    if not value.startswith(_PREFIX):
        return False
    parts = value.split("$")
    if len(parts) != 4:
        return False
    if parts[1] != str(_ITERATIONS):
        return False
    return True


def verify_password(password: str, encoded: str) -> bool:
    if not is_hashed_password(encoded):
        return False

    try:
        _, iterations, salt_b64, key_b64 = encoded.split("$", 3)
        salt = _b64decode(salt_b64)
        expected_key = _b64decode(key_b64)
        iterations_int = int(iterations)
    except (TypeError, ValueError):
        return False

    actual_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations_int,
        dklen=len(expected_key),
    )
    return hmac.compare_digest(actual_key, expected_key)
