"""
RBAC permissions: проверка уровня доступа к модулю.

Эффективный уровень доступа membership к модулю:
    1. UserModuleAccessOverride — если есть запись на этот модуль, её level побеждает.
    2. Иначе — максимум среди RolePermission.level по всем UserRole membership-а.
    3. Иначе — NONE.

Иерархия уровней (min_level → допустимые):
    r     : READ, READ_WRITE, ADMIN
    rw    : READ_WRITE, ADMIN
    admin : ADMIN
"""
from rest_framework.permissions import BasePermission


_LEVEL_ORDER = {
    "none": 0,
    "r": 1,
    "rw": 2,
    "admin": 3,
}


def _effective_level(membership, module_code: str) -> str:
    """Вычислить фактический уровень доступа membership к модулю."""
    from apps.rbac.models import AccessLevel, RolePermission, UserModuleAccessOverride

    override = (
        UserModuleAccessOverride.objects.filter(
            membership=membership, module__code=module_code
        )
        .values_list("level", flat=True)
        .first()
    )
    if override is not None:
        return override

    levels = list(
        RolePermission.objects.filter(
            role__in=membership.user_roles.values("role"),
            module__code=module_code,
        ).values_list("level", flat=True)
    )
    if not levels:
        return AccessLevel.NONE

    # берём максимальный
    return max(levels, key=lambda lv: _LEVEL_ORDER.get(lv, 0))


def level_satisfies(actual: str, required: str) -> bool:
    return _LEVEL_ORDER.get(actual, 0) >= _LEVEL_ORDER.get(required, 0)


class HasModulePermission(BasePermission):
    """
    Базовый permission-class, настраиваемый через viewset-атрибуты:
        module_code       — str, код модуля (например "feed", "matochnik")
        required_level    — "r" / "rw" / "admin" (default "r")
        write_level       — уровень для мутирующих методов (default "rw")

    Использование:
        class RecipeViewSet(ModelViewSet):
            permission_classes = [IsAuthenticated, HasModulePermission]
            module_code = "feed"
            required_level = "r"
            write_level = "rw"
    """

    message = "Недостаточно прав на модуль."

    def has_permission(self, request, view):
        membership = getattr(request, "membership", None)
        if membership is None:
            return False

        module_code = getattr(view, "module_code", None)
        if module_code is None:
            # Если viewset не указал — пропускаем (только auth + org-mem достаточно).
            return True

        if request.method in ("GET", "HEAD", "OPTIONS"):
            required = getattr(view, "required_level", "r")
        else:
            required = getattr(view, "write_level", "rw")

        actual = _effective_level(membership, module_code)
        return level_satisfies(actual, required)


def can_see_finances(user, organization, module_code: str = "ledger") -> bool:
    """Проверка: может ли пользователь видеть деньги указанного модуля?

    Видит если есть `r`-доступ к этому модулю ИЛИ к ledger (общефинансовый
    bypass). Используется в endpoint'ах которые отдают агрегированные
    финансовые данные (dashboard summary, cashflow chart, holding consolidation,
    traceability cost) и в `FinancialFieldsMixin` для serializer-уровня.

    Если `module_code='ledger'` (default) — стандартная проверка «может ли
    видеть финансы вообще». Для проверки «может ли видеть финансы конкретного
    модуля» — передайте код этого модуля.
    """
    from apps.organizations.models import OrganizationMembership

    if not user or not user.is_authenticated or not organization:
        return False
    membership = (
        OrganizationMembership.objects.filter(
            user=user, organization=organization, is_active=True,
        ).first()
    )
    if membership is None:
        return False

    if module_code != "ledger":
        own_lvl = _effective_level(membership, module_code)
        if level_satisfies(own_lvl, "r"):
            return True

    ledger_lvl = _effective_level(membership, "ledger")
    return level_satisfies(ledger_lvl, "r")
