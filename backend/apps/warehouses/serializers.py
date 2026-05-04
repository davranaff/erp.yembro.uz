from rest_framework import serializers

from .models import ProductionBlock, StockMovement, Warehouse


class ProductionBlockSerializer(serializers.ModelSerializer):
    module_code = serializers.SerializerMethodField()
    module_name = serializers.SerializerMethodField()
    capacity_unit_code = serializers.SerializerMethodField()

    class Meta:
        model = ProductionBlock
        fields = (
            "id",
            "code",
            "name",
            "module",
            "kind",
            "area_m2",
            "capacity",
            "capacity_unit",
            "is_active",
            "module_code",
            "module_name",
            "capacity_unit_code",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "module_code",
            "module_name",
            "capacity_unit_code",
            "created_at",
            "updated_at",
        )

    def get_module_code(self, obj):
        return obj.module.code if obj.module_id else None

    def get_module_name(self, obj):
        return obj.module.name if obj.module_id else None

    def get_capacity_unit_code(self, obj):
        return obj.capacity_unit.code if obj.capacity_unit_id else None


class WarehouseSerializer(serializers.ModelSerializer):
    module_code = serializers.SerializerMethodField()
    module_name = serializers.SerializerMethodField()
    production_block_code = serializers.SerializerMethodField()
    production_block_name = serializers.SerializerMethodField()
    default_gl_subaccount_code = serializers.SerializerMethodField()
    default_gl_subaccount_name = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = (
            "id",
            "code",
            "name",
            "module",
            "production_block",
            "default_gl_subaccount",
            "is_active",
            "module_code",
            "module_name",
            "production_block_code",
            "production_block_name",
            "default_gl_subaccount_code",
            "default_gl_subaccount_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "module_code",
            "module_name",
            "production_block_code",
            "production_block_name",
            "default_gl_subaccount_code",
            "default_gl_subaccount_name",
            "created_at",
            "updated_at",
        )

    def get_module_code(self, obj):
        return obj.module.code if obj.module_id else None

    def get_module_name(self, obj):
        return obj.module.name if obj.module_id else None

    def get_production_block_code(self, obj):
        return obj.production_block.code if obj.production_block_id else None

    def get_production_block_name(self, obj):
        return obj.production_block.name if obj.production_block_id else None

    def get_default_gl_subaccount_code(self, obj):
        return (
            obj.default_gl_subaccount.code if obj.default_gl_subaccount_id else None
        )

    def get_default_gl_subaccount_name(self, obj):
        return (
            obj.default_gl_subaccount.name if obj.default_gl_subaccount_id else None
        )

    def validate(self, attrs):
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org is None:
            return attrs
        block = attrs.get("production_block") or getattr(
            self.instance, "production_block", None
        )
        if block and block.organization_id != org.id:
            raise serializers.ValidationError(
                {"production_block": "Блок из другой организации."}
            )
        sub = attrs.get("default_gl_subaccount") or getattr(
            self.instance, "default_gl_subaccount", None
        )
        if sub and sub.account.organization_id != org.id:
            raise serializers.ValidationError(
                {"default_gl_subaccount": "Субсчёт из другой организации."}
            )
        return attrs


class StockMovementSerializer(serializers.ModelSerializer):
    module_code = serializers.SerializerMethodField()
    nomenclature_sku = serializers.SerializerMethodField()
    nomenclature_name = serializers.SerializerMethodField()
    warehouse_from_code = serializers.SerializerMethodField()
    warehouse_to_code = serializers.SerializerMethodField()
    counterparty_code = serializers.SerializerMethodField()
    counterparty_name = serializers.SerializerMethodField()
    batch_doc_number = serializers.SerializerMethodField()
    is_manual = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = (
            "id",
            "doc_number",
            "kind",
            "date",
            "module",
            "nomenclature",
            "quantity",
            "unit_price_uzs",
            "amount_uzs",
            "warehouse_from",
            "warehouse_to",
            "counterparty",
            "batch",
            "module_code",
            "nomenclature_sku",
            "nomenclature_name",
            "warehouse_from_code",
            "warehouse_to_code",
            "counterparty_code",
            "counterparty_name",
            "batch_doc_number",
            "is_manual",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields  # только чтение — создаются через сервисы

    def get_module_code(self, obj):
        return obj.module.code if obj.module_id else None

    def get_nomenclature_sku(self, obj):
        return obj.nomenclature.sku if obj.nomenclature_id else None

    def get_nomenclature_name(self, obj):
        return obj.nomenclature.name if obj.nomenclature_id else None

    def get_warehouse_from_code(self, obj):
        return obj.warehouse_from.code if obj.warehouse_from_id else None

    def get_warehouse_to_code(self, obj):
        return obj.warehouse_to.code if obj.warehouse_to_id else None

    def get_counterparty_code(self, obj):
        return obj.counterparty.code if obj.counterparty_id else None

    def get_counterparty_name(self, obj):
        return obj.counterparty.name if obj.counterparty_id else None

    def get_batch_doc_number(self, obj):
        return obj.batch.doc_number if obj.batch_id else None

    def get_is_manual(self, obj):
        return obj.source_content_type_id is None and obj.source_object_id is None


class StockMovementManualCreateSerializer(serializers.Serializer):
    """
    Вход для ручного создания движения по складу.
    POST /api/warehouses/movements/manual/
    """

    module = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=StockMovement.Kind.choices)
    date = serializers.DateTimeField(required=False)
    nomenclature = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    unit_price_uzs = serializers.DecimalField(max_digits=18, decimal_places=2)
    warehouse_from = serializers.UUIDField(required=False, allow_null=True)
    warehouse_to = serializers.UUIDField(required=False, allow_null=True)
    counterparty = serializers.UUIDField(required=False, allow_null=True)
    batch = serializers.UUIDField(required=False, allow_null=True)
