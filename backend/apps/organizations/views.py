from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import (
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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

        # Quick-фильтр «мои подчинённые» (по manager FK). Работает для любой
        # роли — кто себе назначил manager, того и видит. Org-admin тоже
        # имеет «своих» подчинённых, но при my_subordinates=true он не
        # обходит фильтр (логика «мои» — это про дерево manager, а не
        # про admin-доступ).
        if (self.request.query_params.get("my_subordinates") or "").lower() in ("1", "true", "yes"):
            qs = qs.filter(manager__user=self.request.user)
            return qs

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

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        membership = getattr(self.request, "membership", None)
        hr_level = (
            _effective_level(membership, "hr") if membership is not None else None
        )
        ctx["hr_visible"] = bool(
            membership is not None
            and (is_org_admin(membership) or level_satisfies(hr_level, "r"))
        )
        # query-флаги читаются только для list/retrieve (write-операции игнорируют)
        params = getattr(self.request, "query_params", None) or {}
        ctx["include_compensation"] = params.get("include_compensation") in ("1", "true")
        ctx["include_balance"] = params.get("include_balance") in ("1", "true")
        return ctx

    @action(detail=True, methods=["post"])
    def terminate(self, request, pk=None):
        """
        POST /api/memberships/{id}/terminate/ — атомарное увольнение.

        Body (опц.): {"date": "YYYY-MM-DD"} — дата увольнения (default = сегодня).

        Эффект:
            1. is_active=False, work_status=terminated.
            2. Закрываем все open SalaryRate (effective_to=date).
            3. Закрываем все open WorkSchedule (effective_to=date).
            4. Audit_log.

        ПРИМЕЧАНИЕ: позитивный/негативный баланс ЗП НЕ обнуляется автоматически.
        HR должен либо доплатить, либо удержать через PayrollAdjustment.
        """
        from datetime import date as _date, datetime as _datetime
        from django.db import transaction as _tx

        self._require_org_admin()
        membership = self.get_object()

        date_str = request.data.get("date") if hasattr(request, "data") else None
        try:
            term_date = (
                _datetime.strptime(date_str, "%Y-%m-%d").date()
                if date_str else _date.today()
            )
        except ValueError:
            raise ValidationError({"date": "Формат YYYY-MM-DD."})

        from apps.payroll.models import SalaryRate as _SR, WorkSchedule as _WS

        with _tx.atomic():
            membership.is_active = False
            membership.work_status = "terminated"
            membership.save(update_fields=["is_active", "work_status", "updated_at"])
            _SR.objects.filter(
                employee=membership, effective_to__isnull=True
            ).update(effective_to=term_date)
            _WS.objects.filter(
                employee=membership, effective_to__isnull=True
            ).update(effective_to=term_date)
            audit_log(
                organization=membership.organization,
                actor=request.user,
                action=AuditLog.Action.UPDATE,
                entity=membership,
                action_verb=f"terminated {membership.user.email} on {term_date}"[:64],
            )

        # Возвращаем баланс на момент увольнения для UI
        from apps.payroll.services.balance import compute_balance
        bal = compute_balance(membership, term_date)
        return Response({
            "membership_id": str(membership.id),
            "terminated_on": term_date,
            "balance_at_termination": str(bal.balance_uzs),
            "balance_breakdown": {
                "accrued_total": str(bal.accrued_total),
                "paid_total": str(bal.paid_total),
            },
        })

    @action(detail=True, methods=["get"])
    def balance(self, request, pk=None):
        """GET /api/memberships/{id}/balance/?as_of=YYYY-MM-DD"""
        membership = getattr(request, "membership", None)
        if membership is None:
            raise PermissionDenied({"detail": "Нет доступа."})
        if not (
            is_org_admin(membership)
            or level_satisfies(_effective_level(membership, "hr"), "r")
        ):
            raise PermissionDenied({"detail": "Требуется hr:r."})
        employee = self.get_object()
        from datetime import date, datetime

        from apps.payroll.services.balance import compute_balance

        as_of_str = request.query_params.get("as_of")
        if as_of_str:
            try:
                as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date()
            except ValueError:
                raise ValidationError({"as_of": "Формат YYYY-MM-DD."})
        else:
            as_of = date.today()
        bal = compute_balance(employee, as_of)
        return Response({
            "employee_id": bal.employee_id,
            "as_of": bal.as_of,
            "accrued_total": str(bal.accrued_total),
            "paid_total": str(bal.paid_total),
            "adjustments_plus": str(bal.adjustments_plus),
            "adjustments_minus": str(bal.adjustments_minus),
            "balance_uzs": str(bal.balance_uzs),
        })

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

        manager = data.get("manager")
        if manager and manager.organization_id != org.id:
            raise ValidationError({
                "manager": "Руководитель должен быть в той же организации.",
            })

        membership = OrganizationMembership.objects.create(
            user=user,
            organization=org,
            is_active=True,
            position_title=data.get("position_title", ""),
            work_phone=data.get("work_phone", "") or data.get("phone", ""),
            work_status=data.get("work_status", OrganizationMembership.WorkStatus.ACTIVE),
            manager=manager,
        )
        audit_log(
            organization=org,
            actor=self.request.user,
            action=AuditLog.Action.CREATE,
            entity=membership,
            action_verb=f"hired {email} as {data.get('position_title', '—')}",
        )
        serializer.instance = membership
