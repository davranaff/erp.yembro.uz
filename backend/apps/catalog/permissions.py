from rest_framework import permissions


class PublicReadOnly(permissions.BasePermission):
    """GET — анонимно. Любой write → 403 (для путей где они не предусмотрены)."""

    def has_permission(self, request, view) -> bool:
        return request.method in permissions.SAFE_METHODS
