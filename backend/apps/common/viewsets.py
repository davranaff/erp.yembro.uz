"""
Базовые DRF viewset mixins с изоляцией по organization + автоматическим аудитом.
"""
from __future__ import annotations

from typing import Optional

from rest_framework import viewsets
from rest_framework.exceptions import (
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import IsAuthenticated

from .permissions import HasModulePermission


ORGANIZATION_HEADER = "HTTP_X_ORGANIZATION_CODE"


class OrganizationContextMixin:
    """
    Резолвит организацию и membership после аутентификации (в initial()),
    ставит на request:
        request.organization
        request.membership

    Требования:
      - authenticated user (DRF сам вернёт 401 до вызова этого кода)
      - header X-Organization-Code

    Viewset может установить `skip_organization_context = True` если
    endpoint работает без контекста организации (например /users/me).
    """

    skip_organization_context = False

    def initial(self, request, *args, **kwargs):
        # Форматирование/версионирование (из APIView.initial)
        self.format_kwarg = self.get_format_suffix(**kwargs)
        neg = self.perform_content_negotiation(request)
        request.accepted_renderer, request.accepted_media_type = neg
        version, scheme = self.determine_version(request, *args, **kwargs)
        request.version, request.versioning_scheme = version, scheme

        # 1. Authentication (ставит request.user)
        self.perform_authentication(request)

        # 2. Резолв организации ДО проверки permissions,
        #    чтобы HasModulePermission видел request.membership.
        self._resolve_organization(request)

        # 3. Permissions + throttles
        self.check_permissions(request)
        self.check_throttles(request)

    def _resolve_organization(self, request):
        if getattr(self, "skip_organization_context", False):
            return

        user = request.user
        if not user or not user.is_authenticated:
            raise NotAuthenticated()

        code = request.META.get(ORGANIZATION_HEADER, "").strip()
        if not code:
            raise ValidationError(
                {"detail": "Заголовок X-Organization-Code обязателен."}
            )

        from apps.organizations.models import Organization, OrganizationMembership

        try:
            org = Organization.objects.get(code=code, is_active=True)
        except Organization.DoesNotExist:
            raise NotFound({"detail": f"Организация '{code}' не найдена."})

        membership = (
            OrganizationMembership.objects.filter(
                user=user, organization=org, is_active=True
            )
            .select_related("organization")
            .first()
        )
        if not membership:
            raise PermissionDenied(
                {"detail": "У вас нет доступа к этой организации."}
            )

        request.organization = org
        request.membership = membership


class AuditMixin:
    """
    Автоматический AuditLog для CRUD операций ModelViewSet.

    Требует от наследника:
        - self.request.organization (из OrganizationContextMixin)
        - self.module_code: str — код модуля (resolve в Module при записи)

    Использует `apps.audit.services.writer.audit_log()`, который никогда
    не падает (любая ошибка в аудите логируется в warning, не бросается).

    Бизнес-сервисы (confirm_purchase, post_payment и т.д.) пишут СВОЙ
    audit_log через @action с action=POST/UNPOST — они не трогают этот
    миксин и не дублируются.
    """

    # Override на классе если нужно полностью отключить CRUD-аудит
    audit_enabled = True

    def _resolve_audit_module(self):
        code = getattr(self, "module_code", None)
        if not code:
            return None
        from apps.modules.models import Module

        try:
            return Module.objects.get(code=code)
        except Module.DoesNotExist:
            return None

    def _request_meta(self):
        req = getattr(self, "request", None)
        if req is None:
            return None, ""
        ip = req.META.get("REMOTE_ADDR") or req.META.get("HTTP_X_FORWARDED_FOR", "")
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()
        ua = req.META.get("HTTP_USER_AGENT", "")[:255]
        return (ip or None), ua

    def _write_audit(self, action: str, instance, verb: str = ""):
        if not self.audit_enabled:
            return
        from apps.audit.services.writer import audit_log

        org = getattr(self.request, "organization", None)
        actor = getattr(self.request, "user", None)
        if actor and not getattr(actor, "is_authenticated", False):
            actor = None
        module = self._resolve_audit_module()
        ip, ua = self._request_meta()

        audit_log(
            organization=org,
            module=module,
            actor=actor,
            action=action,
            entity=instance,
            action_verb=verb or f"{action} {type(instance).__name__}",
            ip_address=ip,
            user_agent=ua,
        )


class OrganizationScopedMixin(OrganizationContextMixin, AuditMixin):
    """
    Mixin для ModelViewSet: резолвит org-context + фильтрует queryset
    + проставляет organization/created_by при создании + пишет аудит.

    Требует поле `organization` на модели (ForeignKey).
    Если модель имеет поле `created_by` — оно автоматически ставится в
    текущего пользователя.

    Row-level scope (F0.5): viewset может задать `scope_field`, например
    `scope_field = "warehouse_id"`. Тогда queryset дополнительно фильтруется
    через `apps.common.scope.apply_scope()`. По умолчанию scope_field=None
    (фильтр не применяется — поведение совместимо с prev. версией).
    """

    organization_field = "organization"
    scope_field: str | None = None

    def get_queryset(self):
        qs = super().get_queryset()
        org = getattr(self.request, "organization", None)
        if org is None:
            return qs.none()
        qs = qs.filter(**{self.organization_field: org})

        if self.scope_field:
            from .scope import apply_scope, get_user_scope
            user = getattr(self.request, "user", None)
            scope = get_user_scope(user, org)
            qs = apply_scope(qs, scope, scope_field=self.scope_field)
        return qs

    def _save_kwargs_for_create(self, serializer) -> dict:
        """
        Какие дополнительные kwargs передать в serializer.save() при create.
        Ставим organization + created_by (если поле есть).
        """
        org = getattr(self.request, "organization", None)
        kwargs: dict = {}
        if org is not None:
            kwargs[self.organization_field] = org
        model = serializer.Meta.model if hasattr(serializer, "Meta") else None
        if model is None and hasattr(serializer, "child"):
            model = getattr(serializer.child.Meta, "model", None)
        if model is not None:
            field_names = {f.name for f in model._meta.get_fields()}
            if "created_by" in field_names:
                user = getattr(self.request, "user", None)
                if user and getattr(user, "is_authenticated", False):
                    kwargs["created_by"] = user
        return kwargs

    def perform_create(self, serializer):
        instance = serializer.save(**self._save_kwargs_for_create(serializer))
        from apps.audit.models import AuditLog

        self._write_audit(AuditLog.Action.CREATE, instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        from apps.audit.models import AuditLog

        self._write_audit(AuditLog.Action.UPDATE, instance)

    def perform_destroy(self, instance):
        from apps.audit.models import AuditLog

        # Сначала пишем аудит, пока instance ещё существует (__str__).
        # Если миксин определяет _audit_verb_for_delete — используем его (например
        # DeleteReasonMixin добавляет туда reason).
        verb_fn = getattr(self, "_audit_verb_for_delete", None)
        verb = (
            verb_fn(instance) if callable(verb_fn)
            else f"delete {type(instance).__name__} {instance}"
        )
        self._write_audit(AuditLog.Action.DELETE, instance, verb=verb)
        instance.delete()


class OrgScopedModelViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    """Полный CRUD ViewSet с изоляцией по organization + RBAC по модулю + audit."""

    permission_classes = [IsAuthenticated, HasModulePermission]


class ReadOnlyOrgScopedViewSet(
    OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet
):
    """Read-only ViewSet с org-изоляцией + RBAC (без audit для чтения)."""

    permission_classes = [IsAuthenticated, HasModulePermission]


# Alias for consistency with naming in plan
class OrgReadOnlyViewSet(ReadOnlyOrgScopedViewSet):
    """Alias: org-scoped read-only."""


class GlobalReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet для **глобальных** справочников, общих для всех
    организаций (modules, currencies). НЕ требует X-Organization-Code.

    Пример: `apps.modules.ModuleViewSet`, `apps.currency.CurrencyViewSet`.
    """

    permission_classes = [IsAuthenticated]
