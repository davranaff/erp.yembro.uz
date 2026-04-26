from rest_framework import serializers

from apps.currency.serializers import ExchangeRateNestedSerializer

from .models import PurchaseItem, PurchaseOrder


class PurchaseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseItem
        fields = (
            "id",
            "nomenclature",
            "quantity",
            "unit_price",
            "line_total_foreign",
            "line_total_uzs",
        )
        read_only_fields = ("id", "line_total_foreign", "line_total_uzs")


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True, required=False)
    currency_code = serializers.SerializerMethodField()
    counterparty_name = serializers.CharField(source="counterparty.name", read_only=True)
    exchange_rate_source_detail = ExchangeRateNestedSerializer(
        source="exchange_rate_source", read_only=True
    )
    # Опциональный явный курс — если указан в payload, confirm возьмёт его
    # вместо CBU. Сохраняется как `exchange_rate_override` на модели.
    exchange_rate_override = serializers.DecimalField(
        max_digits=18, decimal_places=6, required=False, allow_null=True,
    )

    def get_currency_code(self, obj):
        return obj.currency.code if obj.currency_id else None
    # doc_number — необязателен при create; будет сгенерирован в confirm.
    doc_number = serializers.CharField(
        max_length=32, required=False, allow_blank=True
    )

    class Meta:
        model = PurchaseOrder
        fields = (
            "id",
            "doc_number",
            "date",
            "module",
            "counterparty",
            "counterparty_name",
            "warehouse",
            "status",
            "payment_status",
            "paid_amount_uzs",
            "currency",
            "currency_code",
            "exchange_rate",
            "exchange_rate_source",
            "exchange_rate_source_detail",
            "exchange_rate_override",
            "amount_foreign",
            "amount_uzs",
            "batch",
            "notes",
            "created_at",
            "updated_at",
            "items",
        )
        read_only_fields = (
            "id",
            "status",
            "payment_status",
            "paid_amount_uzs",
            "exchange_rate",
            "exchange_rate_source",
            "exchange_rate_source_detail",
            "amount_foreign",
            "amount_uzs",
            "created_at",
            "updated_at",
        )

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        order = PurchaseOrder.objects.create(**validated_data)
        for item in items_data:
            PurchaseItem.objects.create(order=order, **item)
        return order

    def update(self, instance, validated_data):
        if instance.status != PurchaseOrder.Status.DRAFT:
            raise serializers.ValidationError(
                {"status": "Редактирование возможно только для черновика."}
            )
        items_data = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            # простая замена: удалить старые и создать новые
            instance.items.all().delete()
            for item in items_data:
                PurchaseItem.objects.create(order=instance, **item)
        return instance
