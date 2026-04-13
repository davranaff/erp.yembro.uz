from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Result(Generic[T]):
    ok: bool
    data: Optional[T] = None
    error: Optional[str] = None

    @classmethod
    def ok_result(cls, data: Optional[T] = None) -> "Result[T]":
        return cls(ok=True, data=data)

    @classmethod
    def err(cls, message: str) -> "Result[T]":
        return cls(ok=False, error=message)
