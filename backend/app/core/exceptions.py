from __future__ import annotations


class DomainError(Exception):
    """Base domain error."""


class ValidationError(DomainError):
    """Business-level validation error."""


class ConflictError(DomainError):
    """Operation conflicts with existing persistent state."""


class NotFoundError(DomainError):
    """Entity not found in persistent storage."""


class AccessDeniedError(DomainError):
    """Operation is not allowed for the current actor."""
