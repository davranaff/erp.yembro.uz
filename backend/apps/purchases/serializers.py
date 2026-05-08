from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from apps.currency.serializers import ExchangeRateNestedSerializer

from .models import (
    MAX_PURCHASE_ATTACHMENT_BYTES,
    PurchaseAttachment,
    PurchaseItem,
    PurchaseOrder,
)


class PurchaseItemSerializer(serializers.ModelSerializer):
    nomenclature_name = serializers.CharField(
        source="nomenclature.name", read_only=True,
    )
    nomenclature_sku = serializers.CharField(
        source="nomenclature.sku", read_only=True,
    )
    unit_code = serializers.CharField(
        source="nomenclature.unit.code", read_only=True,
    )

    class Meta:
        model = PurchaseItem
        fields = (
            "id",
            "nomenclature",
            "nomenclature_name",
            "nomenclature_sku",
            "unit_code",
            "quantity",
            "received_qty",
            "unit_price",
            "line_total_foreign",
            "line_total_uzs",
        )
        read_only_fields = (
            "id",
            "nomenclature_name",
            "nomenclature_sku",
            "unit_code",
            "line_total_foreign",
            "line_total_uzs",
        )


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True, required=False)
    currency_code = serializers.SerializerMethodField()
    counterparty_name = serializers.CharField(source="counterparty.name", read_only=True)
    exchange_rate_source_detail = ExchangeRateNestedSerializer(
        source="exchange_rate_source", read_only=True
    )
    content_type_id = serializers.SerializerMethodField()
    # Опциональный явный курс — если указан в payload, confirm возьмёт его
    # вместо CBU. Сохраняется как `exchange_rate_override` на модели.
    exchange_rate_override = serializers.DecimalField(
        max_digits=18, decimal_places=6, required=False, allow_null=True,
    )

    def get_currency_code(self, obj):
        return obj.currency.code if obj.currency_id else None

    def get_content_type_id(self, obj):
        return ContentType.objects.get_for_model(PurchaseOrder).id
    # doc_number — необязателен при create; будет сгенерирован в confirm.
    doc_number = serializers.CharField(
        max_length=32, required=False, allow_blank=True
    )

    class Meta:
        model = PurchaseOrder
        fields = (
            "id",
            "content_type_id",
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
            "content_type_id",
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


class PurchaseAttachmentSerializer(serializers.ModelSerializer):
    """Файл-приложение к закупу.

    Read: возвращает URL файла + метаданные.
    Write: принимает multipart `file` поле, остальные поля автозаполняются
    в perform_create вьюсета (uploaded_by, original_name, size_bytes).
    """

    file_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()
    size_human = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseAttachment
        fields = (
            "id",
            "purchase",
            "file",
            "file_url",
            "original_name",
            "size_bytes",
            "size_human",
            "content_type",
            "description",
            "uploaded_by",
            "uploaded_by_name",
            "created_at",
        )
        read_only_fields = (
            "id",
            "file_url",
            "original_name",
            "size_bytes",
            "size_human",
            "content_type",
            "uploaded_by",
            "uploaded_by_name",
            "created_at",
        )
        extra_kwargs = {"file": {"write_only": True}}

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url

    def get_uploaded_by_name(self, obj):
        if not obj.uploaded_by_id:
            return None
        u = obj.uploaded_by
        return getattr(u, "full_name", None) or getattr(u, "email", None) or str(u)

    def get_size_human(self, obj):
        n = obj.size_bytes or 0
        if n < 1024:
            return f"{n} Б"
        if n < 1024 * 1024:
            return f"{n / 1024:.1f} КБ"
        return f"{n / (1024 * 1024):.1f} МБ"

    def validate_file(self, value):
        # Дублируем проверку размера здесь (не только в clean()) — чтобы
        # отдать клиенту понятную 400-ошибку с полем.
        if value.size > MAX_PURCHASE_ATTACHMENT_BYTES:
            mb = MAX_PURCHASE_ATTACHMENT_BYTES // (1024 * 1024)
            raise serializers.ValidationError(
                f"Файл больше {mb} МБ. Размер: {value.size / (1024 * 1024):.1f} МБ."
            )
        return value
