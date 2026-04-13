from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

from app.repositories.base import BaseRepository as CoreBaseRepository
from app.services.base import BaseService as CoreBaseService
from app.utils.result import Result

T = TypeVar("T")


@dataclass(frozen=True)
class OperationResult(Generic[T]):
    """Backward-compatible operation envelope used by older modules."""

    ok: bool
    value: Optional[T] = None
    error: Optional[str] = None

    @classmethod
    def success(cls, value: Optional[T] = None) -> "OperationResult[T]":
        return cls(ok=True, value=value)

    @classmethod
    def failure(cls, error: str) -> "OperationResult[T]":
        return cls(ok=False, error=error)


class AppError(Exception):
    def __init__(self, message: str, code: str = "app_error"):
        super().__init__(message)
        self.code = code


# Compatibility aliases
BaseRepository = CoreBaseRepository
BaseService = CoreBaseService
BaseRepositoryLegacy = CoreBaseRepository
BaseServiceLegacy = CoreBaseService
ResultLegacy = Result
