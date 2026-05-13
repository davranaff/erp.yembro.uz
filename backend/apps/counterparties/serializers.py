from decimal import Decimal

from rest_framework import serializers

from .models import Counterparty


class CounterpartySerializer(serializers.ModelSerializer):
    # Реальный текущий долг: outstanding по непогашенным SaleOrder/PurchaseOrder
    # (включая синтетический OPENING_BALANCE SO от opening_debt_uzs). Если в БД
    # такого SO ещё нет (imported opening_debt руками) — fallback на
    # opening_debt_uzs, чтобы не показывать 0 для свежемигрированных клиентов.
    # Знак сохраняется как balance_uzs: для buyer + = клиент нам должен,
    # для supplier + = мы должны.
    current_debt_uzs = serializers.SerializerMethodField()
    # code автогенерируется в viewset.perform_create если не задан
    # (К-NNN для покупателей, КС-NNN для поставщиков, КП-NNN для прочих).
    code = serializers.CharField(max_length=32, required=False, allow_blank=True)

    class Meta:
        model = Counterparty
        fields = (
            "id",
            "code",
            "kind",
            "name",
            "inn",
            "specialization",
            "phone",
            "email",
            "address",
            "balance_uzs",
            "current_debt_uzs",
            "credit_limit_uzs",
            "max_overdue_days",
            "opening_debt_uzs",
            "opening_balance_date",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id", "balance_uzs", "current_debt_uzs", "created_at", "updated_at",
        )

    def get_current_debt_uzs(self, obj) -> str:
        debt_map = (self.context or {}).get("current_debt_map")
        if debt_map is not None and obj.id in debt_map:
            return str(debt_map[obj.id])
        # Fallback: opening_debt_uzs ещё не материализован в SaleOrder, либо
        # view не передал debt_map. Лучше показать что-то, чем 0.
        return str(obj.opening_debt_uzs or Decimal("0"))
