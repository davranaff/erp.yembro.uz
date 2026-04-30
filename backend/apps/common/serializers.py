"""
Переиспользуемые serializer-миксины.

В предыдущей версии здесь был FKDisplayMixin, который динамически
добавлял поля-дисплеи через __init__. Он оказался несовместим с DRF
ModelSerializer — DRF резолвит каждое имя из Meta.fields как поле
модели, и наши динамические SerializerMethodField вызывали
ImproperlyConfigured.

Принятое решение: объявлять поля-дисплеи явно в каждом сериализаторе
через serializers.CharField(source="fk.attr", read_only=True) или
SerializerMethodField. См. apps.nomenclature.serializers.
"""
from __future__ import annotations


class OrganizationContextSerializerMixin:
    """Хелпер для извлечения request.organization из context."""

    def _get_organization(self):
        request = self.context.get("request")
        return getattr(request, "organization", None) if request else None


class FinancialFieldsMixin:
    """Скрывает поля с денежными значениями от пользователей которые не имеют
    доступа к **модулю-владельцу** этих денег.

    Принцип: «деньги принадлежат модулю». Цены сырья и себестоимость корма —
    деньги модуля `feed`. Закупочные цены лекарств — модуля `vet`. Cost-per-bird
    партии — модуля `feedlot`. Полная картина (все деньги всех модулей) — у
    бухгалтера с `ledger`.

    Видимость денег = (доступ к модулю-владельцу >= 'r')
                    OR (доступ к 'ledger' >= 'r')
                    OR (где-то 'admin' уровень).

    Подклассы задают:
        financial_fields: tuple[str, ...]      — список полей _uzs
        finances_module: str | None = "ledger" — модуль-владелец денег

    Если `finances_module` не задан — fallback на 'ledger' (как было).

    Для **динамического** модуля (когда поле может принадлежать разным модулям
    в зависимости от instance — например `Batch.accumulated_cost_uzs` зависит
    от `instance.current_module`), переопределите метод
    `get_finances_module(instance) -> str | None`.

    Использование:
        class RawMaterialBatchSerializer(FinancialFieldsMixin, ModelSerializer):
            financial_fields = ("price_per_unit_uzs", "total_cost_uzs")
            finances_module = "feed"  # цены кормов = деньги feed-модуля

    Кешируем результат проверки прав на уровне request — один SQL независимо
    от размера списка.

    Default-allow для backend-internal вызовов (без request в context):
    тесты/админка/shell видят всё.
    """

    financial_fields: tuple[str, ...] = ()
    # Если None — поле берётся динамически через get_finances_module()
    finances_module: str | None = "ledger"

    def get_finances_module(self, instance) -> str | None:
        """Override-point: вернуть модуль для конкретного instance.
        По умолчанию — статичный `finances_module` класса."""
        return self.finances_module

    def to_representation(self, instance):
        data = super().to_representation(instance)
        module = self.get_finances_module(instance)
        visible = self._user_can_see_finances(module)
        if not visible:
            for field in self.financial_fields:
                if field in data:
                    data[field] = None
        if self.financial_fields:
            data["_finances_visible"] = visible
        return data

    def _user_can_see_finances(self, module_code: str | None) -> bool:
        """Юзер видит деньги если у него есть `r`-доступ либо к
        `module_code` (свой модуль), либо к `ledger` (общефинансовый)."""
        request = self.context.get("request")
        if request is None:
            return True  # backend-internal — default-allow
        user = getattr(request, "user", None)
        org = getattr(request, "organization", None)
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if not org:
            return True

        # Кеш per-request per-(org, module): один SQL для всего списка
        cache_key = f"_can_see_finances_{org.id}_{module_code or 'ledger'}"
        cached = getattr(request, cache_key, None)
        if cached is not None:
            return cached

        from apps.common.permissions import _effective_level, level_satisfies
        from apps.organizations.models import OrganizationMembership

        membership = (
            OrganizationMembership.objects
            .filter(user=user, organization=org, is_active=True)
            .first()
        )
        if membership is None:
            result = False
        else:
            # 1) свой модуль (если задан)
            own_ok = False
            if module_code:
                own_lvl = _effective_level(membership, module_code)
                own_ok = level_satisfies(own_lvl, "r")
            # 2) ledger как общефинансовый bypass
            ledger_lvl = _effective_level(membership, "ledger")
            ledger_ok = level_satisfies(ledger_lvl, "r")
            result = own_ok or ledger_ok

        setattr(request, cache_key, result)
        return result
