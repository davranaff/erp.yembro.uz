from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.common.permissions import SYSTEM_MODULES
from apps.common.viewsets import GlobalReadOnlyViewSet, OrgScopedModelViewSet

from .models import Module, OrganizationModule
from .serializers import ModuleSerializer, OrganizationModuleSerializer


class ModuleViewSet(GlobalReadOnlyViewSet):
    """
    /api/modules/ — глобальный справочник модулей (read-only).
    НЕ требует X-Organization-Code.
    """

    serializer_class = ModuleSerializer
    queryset = Module.objects.all().order_by("sort_order", "code")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["kind", "is_active"]
    search_fields = ["code", "name"]
    lookup_field = "code"
    lookup_value_regex = "[a-z_]+"


class OrganizationModuleViewSet(OrgScopedModelViewSet):
    """
    /api/organization-modules/ — какие модули включены для текущей организации.

    GET     — любому члену (read-only по level='r' на 'admin').
    PATCH   — требуется 'rw' на модуль 'admin': включить / отключить / поменять settings_json.
    CREATE/DELETE отключены — список фиксируется миграцией, toggle через `is_enabled`.
    """

    serializer_class = OrganizationModuleSerializer
    queryset = OrganizationModule.objects.select_related("module")
    module_code = "admin"
    required_level = "r"
    write_level = "rw"
    http_method_names = ["get", "patch", "head", "options"]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_enabled", "module"]

    def perform_update(self, serializer):
        instance = serializer.instance
        was_enabled = instance.is_enabled
        new_enabled = serializer.validated_data.get("is_enabled", was_enabled)
        # Блокируем выключение системных модулей — иначе owner залочит сам
        # себя из админки/учёта/справочников. См. SYSTEM_MODULES.
        if instance.module.code in SYSTEM_MODULES and not new_enabled:
            raise DRFValidationError({
                "is_enabled": (
                    f"Модуль «{instance.module.code}» — системный, "
                    f"его нельзя отключить."
                ),
            })
        if not was_enabled and new_enabled and not instance.enabled_at:
            serializer.validated_data.setdefault("enabled_at", timezone.now())
        updated = serializer.save()
        audit_log(
            organization=updated.organization,
            module=updated.module,
            actor=self.request.user,
            action=AuditLog.Action.UPDATE,
            entity=updated,
            action_verb=(
                f"toggled module {updated.module.code} -> "
                f"{'on' if updated.is_enabled else 'off'}"
            ),
        )
