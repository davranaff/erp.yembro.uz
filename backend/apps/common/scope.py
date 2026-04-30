"""
Row-level scope для multi-department организаций (F0.5).

Поверх module-level RBAC (`HasModulePermission`) добавляет фильтр по
конкретным объектам: «этот финансист видит кассы только своего отдела».

## Поведение по умолчанию

Если в `UserScopeAssignment` нет записей для пары (user, organization) —
пользователь имеет **полный** scope: видит все warehouses/blocks орги.
Это значит маленькая ферма с одним отделом не должна ничего настраивать
дополнительно: row-level scope «бездействует».

Как только админ добавил хотя бы одну запись `UserScopeAssignment` для
этого пользователя — переходим в **строгий** режим: видны только явно
назначенные объекты этого типа.

## Как использовать в viewset'ах

```python
class CashboxAccountViewSet(OrgScopedModelViewSet):
    module_code = "ledger"
    scope_field = "warehouse_id"  # ← добавить эту строку

    # get_queryset() автоматически добавит фильтр через apply_scope()
```

Если поле `scope_field` не задано — viewset работает как раньше (без
фильтра). Это позволяет точечно включать row-level scope только там, где
он реально нужен (касса, склад, производственный блок).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Optional


@dataclass(frozen=True)
class UserScope:
    """Изолированный scope конкретного пользователя в конкретной организации.

    `None` в полях `allowed_*_ids` означает «без ограничения по этому типу»
    (нет назначений → видит всё). `frozenset()` (пустой) означает «явно нет
    доступа» — пользователь не должен видеть ни одного объекта этого типа.
    Различие важно: пустой набор и None дают разное поведение.
    """

    allowed_warehouse_ids: Optional[FrozenSet[str]]
    allowed_block_ids: Optional[FrozenSet[str]]
    is_org_admin: bool = False

    @property
    def is_unlimited(self) -> bool:
        """True когда нет ни одного scope-ограничения."""
        return (
            self.is_org_admin
            or (self.allowed_warehouse_ids is None and self.allowed_block_ids is None)
        )


def get_user_scope(user, organization) -> UserScope:
    """Резолвит UserScope для пары (user, org) с одним SQL-запросом."""
    from apps.organizations.models import OrganizationMembership
    from apps.rbac.models import UserScopeAssignment

    if not user or not organization:
        return UserScope(
            allowed_warehouse_ids=frozenset(),
            allowed_block_ids=frozenset(),
        )

    # Org-admin: имеет уровень ADMIN на каком-либо модуле через override —
    # пропускаем все scope-фильтры. Для строгости: можно завести
    # отдельный флаг is_org_admin на membership; пока используем эвристику
    # «есть хоть один админский модуль» как достаточный признак.
    membership = (
        OrganizationMembership.objects.filter(
            user=user, organization=organization, is_active=True,
        ).first()
    )
    if membership is None:
        return UserScope(
            allowed_warehouse_ids=frozenset(),
            allowed_block_ids=frozenset(),
        )

    is_admin = membership.module_overrides.filter(level="admin").exists()
    if is_admin:
        return UserScope(
            allowed_warehouse_ids=None,
            allowed_block_ids=None,
            is_org_admin=True,
        )

    assignments = list(
        UserScopeAssignment.objects.filter(
            organization=organization, user=user,
        ).values_list("scope_type", "scope_id")
    )

    if not assignments:
        # Нет ни одного назначения → unlimited (default-поведение)
        return UserScope(
            allowed_warehouse_ids=None,
            allowed_block_ids=None,
        )

    warehouses: set[str] = set()
    blocks: set[str] = set()
    for scope_type, scope_id in assignments:
        if scope_type == "warehouse":
            warehouses.add(str(scope_id))
        elif scope_type == "production_block":
            blocks.add(str(scope_id))

    return UserScope(
        allowed_warehouse_ids=frozenset(warehouses) if warehouses else None,
        allowed_block_ids=frozenset(blocks) if blocks else None,
    )


def apply_scope(queryset, scope: UserScope, *, scope_field: str):
    """Применить scope-фильтр к queryset по полю.

    `scope_field` — имя поля в модели, например `"warehouse_id"` или
    `"production_block_id"`. Если scope unlimited — queryset без изменений.
    """
    if scope.is_unlimited:
        return queryset

    if scope_field.endswith("warehouse_id") or scope_field == "warehouse":
        ids = scope.allowed_warehouse_ids
    elif scope_field.endswith("block_id") or scope_field.endswith("production_block_id"):
        ids = scope.allowed_block_ids
    else:
        # Неизвестное поле — не применяем (чтобы не схлопнуть всё в .none()
        # из-за опечатки в scope_field).
        return queryset

    if ids is None:
        return queryset
    if not ids:
        return queryset.none()
    return queryset.filter(**{f"{scope_field}__in": list(ids)})
