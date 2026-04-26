from rest_framework import serializers

from apps.currency.serializers import ExchangeRateNestedSerializer

from .models import Payment, PaymentAllocation


class PaymentAllocationSerializer(serializers.ModelSerializer):
    target_model = serializers.CharField(
        source="target_content_type.model", read_only=True
    )

    class Meta:
        model = PaymentAllocation
        fields = (
            "id",
            "target_content_type",
            "target_model",
            "target_object_id",
            "amount_uzs",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "target_model", "created_at")


class PaymentSerializer(serializers.ModelSerializer):
    allocations = PaymentAllocationSerializer(many=True, read_only=True)
    currency_code = serializers.SerializerMethodField()
    counterparty_name = serializers.CharField(
        source="counterparty.name", read_only=True, default=None, allow_null=True,
    )
    cash_subaccount_code = serializers.CharField(
        source="cash_subaccount.code", read_only=True, default=None, allow_null=True,
    )
    cash_subaccount_name = serializers.CharField(
        source="cash_subaccount.name", read_only=True, default=None, allow_null=True,
    )
    contra_subaccount_code = serializers.CharField(
        source="contra_subaccount.code", read_only=True, default=None, allow_null=True,
    )
    contra_subaccount_name = serializers.CharField(
        source="contra_subaccount.name", read_only=True, default=None, allow_null=True,
    )
    expense_article_code = serializers.CharField(
        source="expense_article.code", read_only=True, default=None, allow_null=True,
    )
    expense_article_name = serializers.CharField(
        source="expense_article.name", read_only=True, default=None, allow_null=True,
    )
    module_code = serializers.CharField(
        source="module.code", read_only=True, default=None, allow_null=True,
    )
    exchange_rate_source_detail = ExchangeRateNestedSerializer(
        source="exchange_rate_source", read_only=True
    )
    # doc_number генерируется в сервисе post — при create не обязателен
    doc_number = serializers.CharField(
        max_length=32, required=False, allow_blank=True
    )

    class Meta:
        model = Payment
        fields = (
            "id",
            "doc_number",
            "date",
            "module",
            "module_code",
            "direction",
            "channel",
            "kind",
            "status",
            "counterparty",
            "counterparty_name",
            "currency",
            "currency_code",
            "exchange_rate",
            "exchange_rate_source",
            "exchange_rate_source_detail",
            "amount_foreign",
            "amount_uzs",
            "cash_subaccount",
            "cash_subaccount_code",
            "cash_subaccount_name",
            "contra_subaccount",
            "contra_subaccount_code",
            "contra_subaccount_name",
            "expense_article",
            "expense_article_code",
            "expense_article_name",
            "journal_entry",
            "posted_at",
            "notes",
            "created_at",
            "updated_at",
            "allocations",
        )
        read_only_fields = (
            "id",
            "status",
            "journal_entry",
            "posted_at",
            "created_at",
            "updated_at",
            "module_code",
            "counterparty_name",
            "cash_subaccount_code",
            "cash_subaccount_name",
            "contra_subaccount_code",
            "contra_subaccount_name",
            "expense_article_code",
            "expense_article_name",
        )

    def get_currency_code(self, obj):
        return obj.currency.code if obj.currency_id else None

    def validate(self, attrs):
        # Запрет редактирования после POSTED — руками, не через modelform
        if self.instance and self.instance.status == Payment.Status.POSTED:
            raise serializers.ValidationError(
                {"status": "Проведённый платёж нельзя редактировать."}
            )
        return attrs
