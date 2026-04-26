from rest_framework import serializers

from .models import Currency, ExchangeRate, IntegrationSyncLog


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = (
            "id",
            "code",
            "numeric_code",
            "name_ru",
            "name_en",
            "is_active",
        )
        read_only_fields = fields


class ExchangeRateNestedSerializer(serializers.ModelSerializer):
    """
    Компактная вложенная версия — для передачи внутри других документов
    (PurchaseOrder, SaleOrder, Payment, JournalEntry), чтобы фронт мог
    показать «курс был получен из cbu.uz, дата ЦБ DD.MM.YYYY, fetched в
    HH:MM» без дополнительного запроса.
    """

    currency_code = serializers.CharField(source="currency.code", read_only=True)

    class Meta:
        model = ExchangeRate
        fields = (
            "id",
            "currency_code",
            "date",
            "rate",
            "nominal",
            "source",
            "fetched_at",
        )
        read_only_fields = fields


class ExchangeRateSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source="currency.code", read_only=True)

    class Meta:
        model = ExchangeRate
        fields = (
            "id",
            "currency",
            "currency_code",
            "date",
            "rate",
            "nominal",
            "source",
            "fetched_at",
        )
        read_only_fields = fields


class IntegrationSyncLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationSyncLog
        fields = (
            "id",
            "provider",
            "status",
            "occurred_at",
            "triggered_by",
            "stats",
            "error_message",
        )
        read_only_fields = fields
