"""
Row-level scope для multi-department / multi-module организаций.

Поверх module-level RBAC (`HasModulePermission`) добавляет фильтр по
конкретным объектам: «этот финансист видит кассы только своего отдела»
или «этот finance_head видит только feed-модуль».

## Поведение по умолчанию

Если в `UserScopeAssignment` нет записей для пары (user, organization) —
пользователь имеет **полный** scope: видит все warehouses/blocks/modules
организации. Это значит маленькая ферма с одним отделом / одним модулем
не должна ничего настраивать дополнительно — row-level scope «бездействует».

Как только админ добавил хотя бы одну запись `UserScopeAssignment` — для
**этого измерения** (warehouse/block/module) переходим в **строгий** режим:
видны только явно назначенные объекты этого типа. Другие измерения
остаются unlimited.

### Важно про admin

В прошлой версии любой пользователь с admin-уровнем на каком-либо модуле
автоматически считался `is_org_admin` и обходил scope. Это конфликтовало
с задачей «несколько head-of-finance по модулям, scope не должны
пересекаться». Теперь: **если у пользователя есть хоть одна
UserScopeAssignment-запись, она применяется строго — даже к admin'у.**
Admin-bypass работает только при полном отсутствии назначений.

## Как использовать в viewset'ах

```python
class SaleOrderViewSet(OrgScopedModelViewSet):
    module_code = "sales"
    scope_fields = ("module_id",)   # row-level фильтр по модулю
```

Можно указать несколько полей одновременно, тогда фильтры применяются
по AND. Если scope_fields пустой/None — viewset работает как раньше.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Optional


@dataclass(frozen=True)
class UserScope:
    """Изолированный scope конкретного пользователя в конкретной организации.

    `None` в полях `allowed_*_ids` означает «без ограничения по этому
    измерению» (нет назначений для этого типа → видит всё). `frozenset()`
    (пустой) означает «явно нет доступа» — пользователь не должен видеть
    ни одного объекта этого типа. Различие важно: пустой набор и None
    дают разное поведение.
    """

    allowed_warehouse_ids: Optional[FrozenSet[str]]
    allowed_block_ids: Optional[FrozenSet[str]]
    allowed_module_ids: Optional[FrozenSet[str]] = None
    is_org_admin: bool = False

    @property
    def is_unlimited(self) -> bool:
        """True когда нет ни одного scope-ограничения по всем измерениям."""
        return (
            self.is_org_admin
            or (
                self.allowed_warehouse_ids is None
                and self.allowed_block_ids is None
                and self.allowed_module_ids is None
            )
        )


def get_user_scope(user, organization) -> UserScope:
    """Резолвит UserScope для пары (user, org).

    Логика:
      1. Если нет user/org → пустой scope (видит ничего).
      2. Если нет UserScopeAssignment-записей → проверяем is_admin;
         admin → unlimited, обычный пользователь → unlimited (default).
      3. Если есть хоть одна запись → строгий режим по этим измерениям,
         **даже для admin'а** (см. docstring модуля).
    """
    from apps.organizations.models import OrganizationMembership
    from apps.rbac.models import UserScopeAssignment

    if not user or not organization:
        return UserScope(
            allowed_warehouse_ids=frozenset(),
            allowed_block_ids=frozenset(),
            allowed_module_ids=frozenset(),
        )

    membership = (
        OrganizationMembership.objects.filter(
            user=user, organization=organization, is_active=True,
        ).first()
    )
    if membership is None:
        return UserScope(
            allowed_warehouse_ids=frozenset(),
            allowed_block_ids=frozenset(),
            allowed_module_ids=frozenset(),
        )

    assignments = list(
        UserScopeAssignment.objects.filter(
            organization=organization, user=user,
        ).values_list("scope_type", "scope_id")
    )

    if not assignments:
        # Нет ни одного назначения → default unlimited (admin или нет —
        # неважно, доступ ко всем измерениям).
        return UserScope(
            allowed_warehouse_ids=None,
            allowed_block_ids=None,
            allowed_module_ids=None,
            is_org_admin=membership.module_overrides.filter(level="admin").exists(),
        )

    warehouses: set[str] = set()
    blocks: set[str] = set()
    modules: set[str] = set()
    for scope_type, scope_id in assignments:
        if scope_type == "warehouse":
            warehouses.add(str(scope_id))
        elif scope_type == "production_block":
            blocks.add(str(scope_id))
        elif scope_type == "module":
            modules.add(str(scope_id))

    return UserScope(
        allowed_warehouse_ids=frozenset(warehouses) if warehouses else None,
        allowed_block_ids=frozenset(blocks) if blocks else None,
        allowed_module_ids=frozenset(modules) if modules else None,
        is_org_admin=False,
    )


def _ids_for_field(scope: UserScope, scope_field: str) -> Optional[FrozenSet[str]]:
    if scope_field.endswith("warehouse_id") or scope_field == "warehouse":
        return scope.allowed_warehouse_ids
    if scope_field.endswith("block_id") or scope_field.endswith("production_block_id"):
        return scope.allowed_block_ids
    if scope_field.endswith("module_id") or scope_field == "module":
        return scope.allowed_module_ids
    return None  # неизвестное поле — без фильтра


def apply_scope(queryset, scope: UserScope, *, scope_field=None, scope_fields=None):
    """Применить scope-фильтр к queryset по одному или нескольким полям.

    `scope_field` — единственное имя поля (legacy, для совместимости).
    `scope_fields` — кортеж/список имён полей; фильтр применяется по AND
    для каждого поля независимо.

    Если scope unlimited — queryset без изменений. Если на любом
    измерении явно empty (frozenset()) и поле декларировано — вернётся
    `queryset.none()`.
    """
    if scope.is_unlimited:
        return queryset

    if scope_fields is None:
        scope_fields = (scope_field,) if scope_field else ()
    elif isinstance(scope_fields, str):
        scope_fields = (scope_fields,)

    for field in scope_fields:
        if not field:
            continue
        ids = _ids_for_field(scope, field)
        if ids is None:
            # Нет ограничения на этом измерении — пропускаем.
            continue
        if not ids:
            return queryset.none()
        queryset = queryset.filter(**{f"{field}__in": list(ids)})
    return queryset
