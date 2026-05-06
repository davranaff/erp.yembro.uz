from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.common.permissions import (
    HasAnyModuleRw,
    _effective_level,
    get_user_rw_module_codes,
    is_org_admin,
    level_satisfies,
)
from apps.common.viewsets import OrgScopedModelViewSet
from apps.users.models import User

from .models import Organization, OrganizationMembership
from .serializers import (
    OrganizationMembershipCreateSerializer,
    OrganizationMembershipSerializer,
    OrganizationSerializer,
)


class OrganizationViewSet(viewsets.ModelViewSet):
    """
    /api/organizations/         — список организаций текущего юзера.
    /api/organizations/<code>/  — retrieve / partial_update.

    Чтение разрешено любому member-у. Для PATCH/PUT требуется уровень
    доступа 'rw' (или выше) на модуль 'admin' в соответствующей org.
    Создание/удаление отключены — организации создаются через admin-site.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer
    lookup_field = "code"
    lookup_value_regex = r"[A-Za-z0-9_\-]+"
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Organization.objects.none()
        return (
            Organization.objects.filter(
                memberships__user=user, memberships__is_active=True
            )
            .select_related("accounting_currency")
            .order_by("code")
            .distinct()
        )

    def _check_admin(self, organization: Organization) -> None:
        """Проверяет, что у юзера уровень 'rw' или выше на модуль 'admin'."""
        membership = OrganizationMembership.objects.filter(
            user=self.request.user, organization=organization, is_active=True
        ).first()
        if membership is None:
            raise PermissionDenied({"detail": "Нет доступа к организации."})
        actual = _effective_level(membership, "admin")
        if not level_satisfies(actual, "rw"):
            raise PermissionDenied(
                {"detail": "Недостаточно прав на редактирование организации."}
            )

    def perform_update(self, serializer):
        self._check_admin(serializer.instance)
        instance = serializer.save()
        audit_log(
            organization=instance,
            actor=self.request.user,
            action=AuditLog.Action.UPDATE,
            entity=instance,
            action_verb=f"updated organization {instance.code}",
        )


class OrganizationMembershipViewSet(OrgScopedModelViewSet):
    """
    /api/memberships/ — CRUD сотрудников текущей организации.

    Доступ:
        - READ (list/retrieve): любому head'у модуля (rw на ≥ 1 модуль).
          Queryset скоупится — head видит только сотрудников, у которых
          есть rw-перекрытие с его модулями (например feed_head видит
          тех, у кого тоже есть feed:rw).
        - WRITE (create/update/delete): только org-admin (любой override
          level=admin) — управление кадрами не делегируется head'ам, чтобы
          избежать privilege escalation.

    Org-admin (любой модуль admin-override) видит и редактирует всех.

    Создание: тело `{email, full_name, phone, password, position_title,
    work_phone, work_status}` — создаётся User (если такого email ещё нет)
    и membership в текущей organization. Существующий User переиспользуется.

    Удаление: soft-delete через `is_active=False` (безопаснее хард-delete).
    """

    permission_classes = [IsAuthenticated, HasAnyModuleRw]
    queryset = OrganizationMembership.objects.select_related("user", "organization")
    # module_code/required/write_level не задаём — кастомная логика ниже.
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active", "work_status"]
    search_fields = [
        "user__email",
        "user__full_name",
        "position_title",
        "work_phone",
    ]
    ordering_fields = ["joined_at", "user__full_name"]
    ordering = ["user__full_name"]

    def _require_org_admin(self):
        """
        WRITE-операции требуют org-admin (admin-override на ≥ 1 модуле).
        Heads — только READ.
        """
        membership = getattr(self.request, "membership", None)
        if membership is None or not is_org_admin(membership):
            raise PermissionDenied(
                {"detail": "Управление сотрудниками — только для администратора организации."}
            )

    def get_queryset(self):
        qs = super().get_queryset()
        membership = getattr(self.request, "membership", None)
        if membership is None:
            return qs.none()
        if is_org_admin(membership):
            return qs

        # Head видит только сотрудников, у которых пересекаются модули.
        # «Пересекаются» = у их membership есть override/role с любым level
        # на хотя бы один из модулей текущего юзера.
        my_modules = get_user_rw_module_codes(membership)
        if not my_modules:
            return qs.none()

        from apps.rbac.models import RolePermission, UserModuleAccessOverride

        peer_membership_ids: set[str] = set()
        peer_membership_ids.update(
            UserModuleAccessOverride.objects.filter(
                module__code__in=my_modules,
            ).values_list("membership_id", flat=True)
        )
        peer_membership_ids.update(
            RolePermission.objects.filter(
                module__code__in=my_modules,
            ).values_list("role__assignments__membership_id", flat=True)
        )
        # Свой membership всегда виден
        peer_membership_ids.add(membership.id)
        peer_membership_ids.discard(None)
        return qs.filter(id__in=peer_membership_ids)

    def get_serializer_class(self):
        if self.action == "create":
            return OrganizationMembershipCreateSerializer
        return OrganizationMembershipSerializer

    def update(self, request, *args, **kwargs):
        self._require_org_admin()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._require_org_admin()
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._require_org_admin()
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        self._require_org_admin()
        org = self.request.organization
        data = serializer.validated_data
        email = data["email"].lower().strip()
        full_name = data["full_name"].strip()

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create(
                email=email,
                full_name=full_name,
                phone=data.get("phone", ""),
                is_active=True,
            )
            if data.get("password"):
                user.set_password(data["password"])
            else:
                user.set_unusable_password()
            user.save()
        else:
            changed = False
            if full_name and user.full_name != full_name:
                user.full_name = full_name
                changed = True
            if data.get("phone") and user.phone != data["phone"]:
                user.phone = data["phone"]
                changed = True
            if changed:
                user.save(update_fields=["full_name", "phone"])

        if OrganizationMembership.objects.filter(user=user, organization=org).exists():
            raise ValidationError(
                {"email": "Этот пользователь уже сотрудник компании."}
            )

        membership = OrganizationMembership.objects.create(
            user=user,
            organization=org,
            is_active=True,
            position_title=data.get("position_title", ""),
            work_phone=data.get("work_phone", "") or data.get("phone", ""),
            work_status=data.get("work_status", OrganizationMembership.WorkStatus.ACTIVE),
        )
        audit_log(
            organization=org,
            actor=self.request.user,
            action=AuditLog.Action.CREATE,
            entity=membership,
            action_verb=f"hired {email} as {data.get('position_title', '—')}",
        )
        serializer.instance = membership
