"""
RBAC ViewSet'ы.

Все мутации (создание/изменение/удаление RolePermission, UserRole,
UserModuleAccessOverride) пишут в `AuditLog` запись с
`action=PERMISSION_CHANGE`. Это делает изменения прав видимыми в журнале
аудита и закрывает требование «кто что когда изменил».

Generic CRUD-аудит (`AuditMixin`) на этих viewset'ах отключён через
`audit_enabled = False` — мы пишем свои более информативные записи
(level старого/нового, целевой пользователь и т.д.).
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.common.viewsets import OrgScopedModelViewSet

from .models import Role, RolePermission, UserModuleAccessOverride, UserRole
from .serializers import (
    RolePermissionSerializer,
    RoleSerializer,
    UserModuleAccessOverrideSerializer,
    UserRoleSerializer,
)


# ─── helpers ──────────────────────────────────────────────────────────────


def _request_meta(request):
    ip = request.META.get("REMOTE_ADDR") or request.META.get("HTTP_X_FORWARDED_FOR", "")
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    ua = request.META.get("HTTP_USER_AGENT", "")[:255]
    return (ip or None), ua


def _audit_permission_change(*, request, organization, entity, verb: str):
    actor = getattr(request, "user", None)
    if actor and not getattr(actor, "is_authenticated", False):
        actor = None
    ip, ua = _request_meta(request)
    audit_log(
        organization=organization,
        actor=actor,
        action=AuditLog.Action.PERMISSION_CHANGE,
        entity=entity,
        action_verb=verb,
        ip_address=ip,
        user_agent=ua,
    )


# ─── ViewSets ─────────────────────────────────────────────────────────────


class RoleViewSet(OrgScopedModelViewSet):
    """/api/rbac/roles/ — CRUD ролей. Generic CRUD-аудит остаётся включён."""

    serializer_class = RoleSerializer
    queryset = Role.objects.prefetch_related("permissions__module")
    module_code = "admin"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_system", "is_active"]
    search_fields = ["code", "name"]
    ordering = ["code"]


class RolePermissionViewSet(OrgScopedModelViewSet):
    """/api/rbac/role-permissions/"""

    serializer_class = RolePermissionSerializer
    queryset = RolePermission.objects.select_related("role", "module")
    module_code = "admin"
    organization_field = "role__organization"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["role", "module", "level"]
    audit_enabled = False  # пишем свой permission_change

    def perform_create(self, serializer):
        # organization_field (`role__organization`) — это путь для get_queryset,
        # не имя поля в модели. У RolePermission нет поля organization напрямую,
        # организация выводится через role. Поэтому save() без extra kwargs.
        instance = serializer.save()
        _audit_permission_change(
            request=self.request,
            organization=instance.role.organization,
            entity=instance.role,
            verb=f"{instance.module.code}: granted {instance.level}",
        )

    def perform_update(self, serializer):
        old_level = serializer.instance.level
        instance = serializer.save()
        if old_level != instance.level:
            _audit_permission_change(
                request=self.request,
                organization=instance.role.organization,
                entity=instance.role,
                verb=f"{instance.module.code}: {old_level}→{instance.level}",
            )

    def perform_destroy(self, instance):
        org = instance.role.organization
        role = instance.role
        module_code = instance.module.code
        instance.delete()
        _audit_permission_change(
            request=self.request,
            organization=org,
            entity=role,
            verb=f"{module_code}: revoked",
        )


class UserRoleViewSet(OrgScopedModelViewSet):
    """/api/rbac/user-roles/"""

    serializer_class = UserRoleSerializer
    queryset = UserRole.objects.select_related(
        "membership__user", "role", "assigned_by"
    )
    module_code = "admin"
    organization_field = "role__organization"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["membership", "role"]
    ordering = ["-assigned_at"]
    audit_enabled = False

    def perform_create(self, serializer):
        # organization наследуется через role.organization (см. clean()).
        # assigned_by ставим явно, чтобы было видно кто назначил.
        kwargs = {}
        user = getattr(self.request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            kwargs["assigned_by"] = user
        instance = serializer.save(**kwargs)
        email = (
            instance.membership.user.email
            if instance.membership_id and instance.membership.user_id
            else "?"
        )
        _audit_permission_change(
            request=self.request,
            organization=instance.role.organization,
            entity=instance.role,
            verb=f"assigned {instance.role.code} to {email}",
        )

    def perform_destroy(self, instance):
        org = instance.role.organization
        role = instance.role
        email = (
            instance.membership.user.email
            if instance.membership_id and instance.membership.user_id
            else "?"
        )
        role_code = role.code
        instance.delete()
        _audit_permission_change(
            request=self.request,
            organization=org,
            entity=role,
            verb=f"revoked {role_code} from {email}",
        )


class UserModuleAccessOverrideViewSet(OrgScopedModelViewSet):
    """/api/rbac/overrides/"""

    serializer_class = UserModuleAccessOverrideSerializer
    queryset = UserModuleAccessOverride.objects.select_related(
        "membership__user", "module"
    )
    module_code = "admin"
    organization_field = "membership__organization"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["membership", "module", "level"]
    audit_enabled = False

    def perform_create(self, serializer):
        # organization выводится через membership.
        instance = serializer.save()
        email = (
            instance.membership.user.email
            if instance.membership_id and instance.membership.user_id
            else "?"
        )
        _audit_permission_change(
            request=self.request,
            organization=instance.membership.organization,
            entity=instance.membership,
            verb=f"override {instance.module.code}: {instance.level} for {email}",
        )

    def perform_update(self, serializer):
        old_level = serializer.instance.level
        instance = serializer.save()
        if old_level != instance.level:
            email = (
                instance.membership.user.email
                if instance.membership_id and instance.membership.user_id
                else "?"
            )
            _audit_permission_change(
                request=self.request,
                organization=instance.membership.organization,
                entity=instance.membership,
                verb=f"override {instance.module.code}: {old_level}→{instance.level} for {email}",
            )

    def perform_destroy(self, instance):
        org = instance.membership.organization
        membership = instance.membership
        module_code = instance.module.code
        email = membership.user.email if membership.user_id else "?"
        instance.delete()
        _audit_permission_change(
            request=self.request,
            organization=org,
            entity=membership,
            verb=f"override {module_code}: removed for {email}",
        )
