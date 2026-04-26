from rest_framework import serializers

from apps.modules.models import Module

from .models import (
    FeedBatch,
    ProductionTask,
    ProductionTaskComponent,
    RawMaterialBatch,
    Recipe,
    RecipeComponent,
    RecipeVersion,
)


# ─── Recipe / Version / Component ─────────────────────────────────────────


class RecipeComponentSerializer(serializers.ModelSerializer):
    nomenclature_sku = serializers.SerializerMethodField()
    nomenclature_name = serializers.SerializerMethodField()
    vet_drug_sku = serializers.SerializerMethodField()

    class Meta:
        model = RecipeComponent
        fields = (
            "id",
            "recipe_version",
            "nomenclature",
            "share_percent",
            "min_share_percent",
            "max_share_percent",
            "protein_override",
            "fat_override",
            "fibre_override",
            "lysine_override",
            "methionine_override",
            "threonine_override",
            "me_kcal_per_kg_override",
            "is_medicated",
            "withdrawal_period_days",
            "vet_drug",
            "sort_order",
            "nomenclature_sku",
            "nomenclature_name",
            "vet_drug_sku",
        )
        read_only_fields = ("id", "nomenclature_sku", "nomenclature_name", "vet_drug_sku")

    def get_nomenclature_sku(self, obj):
        return obj.nomenclature.sku if obj.nomenclature_id else None

    def get_nomenclature_name(self, obj):
        return obj.nomenclature.name if obj.nomenclature_id else None

    def get_vet_drug_sku(self, obj):
        if not obj.vet_drug_id:
            return None
        return obj.vet_drug.nomenclature.sku if obj.vet_drug.nomenclature_id else None


class RecipeVersionSerializer(serializers.ModelSerializer):
    components = RecipeComponentSerializer(many=True, read_only=True)
    recipe_code = serializers.SerializerMethodField()

    class Meta:
        model = RecipeVersion
        fields = (
            "id",
            "recipe",
            "recipe_code",
            "version_number",
            "status",
            "effective_from",
            "target_protein_percent",
            "target_fat_percent",
            "target_fibre_percent",
            "target_lysine_percent",
            "target_methionine_percent",
            "target_threonine_percent",
            "target_me_kcal_per_kg",
            "comment",
            "author",
            "components",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "recipe_code", "components", "created_at", "updated_at")

    def get_recipe_code(self, obj):
        return obj.recipe.code if obj.recipe_id else None


class RecipeSerializer(serializers.ModelSerializer):
    versions_count = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            "id",
            "code",
            "name",
            "direction",
            "age_range",
            "is_medicated",
            "is_active",
            "notes",
            "versions_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "versions_count", "created_at", "updated_at")

    def get_versions_count(self, obj):
        return obj.versions.count()


# ─── Raw material batches ────────────────────────────────────────────────


class RawMaterialBatchSerializer(serializers.ModelSerializer):
    nomenclature_sku = serializers.SerializerMethodField()
    nomenclature_name = serializers.SerializerMethodField()
    supplier_name = serializers.SerializerMethodField()
    warehouse_code = serializers.SerializerMethodField()
    unit_code = serializers.SerializerMethodField()
    total_cost_uzs = serializers.SerializerMethodField()
    # doc_number автогенерируется в perform_create, quantity рассчитывается
    # в create() из gross_weight_kg + усушки. module автозаполняется
    # модулем "feed" в perform_create — фронту не обязательно его передавать.
    doc_number = serializers.CharField(max_length=32, required=False, allow_blank=True)
    quantity = serializers.DecimalField(
        max_digits=18, decimal_places=3, required=False,
    )
    module = serializers.PrimaryKeyRelatedField(
        queryset=Module.objects.all(), required=False,
    )

    class Meta:
        model = RawMaterialBatch
        fields = (
            "id",
            "doc_number",
            "module",
            "nomenclature",
            "supplier",
            "purchase",
            "warehouse",
            "storage_bin",
            "received_date",
            # Веса
            "gross_weight_kg",
            "settlement_weight_kg",
            "quantity",
            "current_quantity",
            # Усушка
            "moisture_pct_actual",
            "moisture_pct_base",
            "dockage_pct_actual",
            "shrinkage_pct",
            # Прочее
            "unit",
            "price_per_unit_uzs",
            "total_cost_uzs",
            "status",
            "quarantine_until",
            "rejection_reason",
            "notes",
            "nomenclature_sku",
            "nomenclature_name",
            "supplier_name",
            "warehouse_code",
            "unit_code",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "settlement_weight_kg",
            "moisture_pct_base",
            "current_quantity",
            "total_cost_uzs",
            "nomenclature_sku",
            "nomenclature_name",
            "supplier_name",
            "warehouse_code",
            "unit_code",
            "created_at",
            "updated_at",
        )

    def get_nomenclature_sku(self, obj):
        return obj.nomenclature.sku if obj.nomenclature_id else None

    def get_nomenclature_name(self, obj):
        return obj.nomenclature.name if obj.nomenclature_id else None

    def get_supplier_name(self, obj):
        return obj.supplier.name if obj.supplier_id else None

    def get_warehouse_code(self, obj):
        return obj.warehouse.code if obj.warehouse_id else None

    def get_unit_code(self, obj):
        return obj.unit.code if obj.unit_id else None

    def get_total_cost_uzs(self, obj):
        from decimal import Decimal
        qty = obj.quantity or Decimal("0")
        price = obj.price_per_unit_uzs or Decimal("0")
        return str((qty * price).quantize(Decimal("0.01")))

    def create(self, validated_data):
        """
        При создании партии сырья — расчёт зачётного веса по формуле Дюваля.

        Логика приоритетов:
          1. gross + moisture_actual заданы → snapshot moisture_base из
             nomenclature, считаем shrinkage по Дювалю + сорность,
             settlement = gross × (1 − shrink/100), quantity = settlement.
          2. gross + shrinkage_pct заданы напрямую → settlement = gross × (1 − sh/100).
          3. Только quantity → settlement = quantity (legacy без расчётов).
        """
        from decimal import Decimal

        from .services.shrinkage import compute_settlement, settlement_from_gross

        gross = validated_data.get("gross_weight_kg")
        moisture_actual = validated_data.get("moisture_pct_actual")
        dockage = validated_data.get("dockage_pct_actual") or Decimal("0")
        direct_shrink = validated_data.get("shrinkage_pct")
        quantity = validated_data.get("quantity")

        nom = validated_data.get("nomenclature")
        moisture_base = nom.base_moisture_pct if nom else None

        # Snapshot базисной влажности
        if moisture_base is not None:
            validated_data["moisture_pct_base"] = moisture_base

        if gross is not None and gross > 0:
            if moisture_actual is not None and moisture_base is not None:
                # Сценарий 1: расчёт по Дювалю
                settlement, total_shrink = compute_settlement(
                    gross_kg=gross,
                    moisture_actual=moisture_actual,
                    moisture_base=moisture_base,
                    dockage_actual=dockage,
                )
                validated_data["settlement_weight_kg"] = settlement
                validated_data["shrinkage_pct"] = total_shrink
                validated_data["quantity"] = settlement
            elif direct_shrink is not None and direct_shrink > 0:
                # Сценарий 2: пользователь сам ввёл %
                settlement = settlement_from_gross(gross, direct_shrink)
                validated_data["settlement_weight_kg"] = settlement
                validated_data["quantity"] = settlement
            else:
                # gross без расчёта — settlement = gross
                validated_data["settlement_weight_kg"] = gross
                validated_data["quantity"] = gross
        elif quantity is not None:
            # Legacy: ввели только quantity
            validated_data["settlement_weight_kg"] = quantity
            validated_data["gross_weight_kg"] = quantity

        # current_quantity всегда == final quantity при создании
        validated_data["current_quantity"] = validated_data.get("quantity")

        return super().create(validated_data)


# ─── Production tasks ────────────────────────────────────────────────────


class ProductionTaskComponentSerializer(serializers.ModelSerializer):
    nomenclature_sku = serializers.SerializerMethodField()
    nomenclature_name = serializers.SerializerMethodField()
    source_batch_doc_number = serializers.SerializerMethodField()

    class Meta:
        model = ProductionTaskComponent
        fields = (
            "id",
            "task",
            "nomenclature",
            "source_batch",
            "planned_quantity",
            "actual_quantity",
            "planned_price_per_unit_uzs",
            "actual_price_per_unit_uzs",
            "lab_result_snapshot",
            "sort_order",
            "nomenclature_sku",
            "nomenclature_name",
            "source_batch_doc_number",
        )
        read_only_fields = (
            "id",
            "nomenclature_sku",
            "nomenclature_name",
            "source_batch_doc_number",
        )

    def get_nomenclature_sku(self, obj):
        return obj.nomenclature.sku if obj.nomenclature_id else None

    def get_nomenclature_name(self, obj):
        return obj.nomenclature.name if obj.nomenclature_id else None

    def get_source_batch_doc_number(self, obj):
        return obj.source_batch.doc_number if obj.source_batch_id else None


class ProductionTaskSerializer(serializers.ModelSerializer):
    components = ProductionTaskComponentSerializer(many=True, read_only=True)
    recipe_code = serializers.SerializerMethodField()
    recipe_version_number = serializers.SerializerMethodField()
    production_line_code = serializers.SerializerMethodField()
    doc_number = serializers.CharField(max_length=32, required=False, allow_blank=True)

    class Meta:
        model = ProductionTask
        fields = (
            "id",
            "doc_number",
            "module",
            "recipe_version",
            "production_line",
            "shift",
            "scheduled_at",
            "started_at",
            "completed_at",
            "planned_quantity_kg",
            "actual_quantity_kg",
            "status",
            "is_medicated",
            "withdrawal_period_days",
            "operator",
            "technologist",
            "notes",
            "recipe_code",
            "recipe_version_number",
            "production_line_code",
            "components",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "started_at",
            "completed_at",
            "actual_quantity_kg",
            "recipe_code",
            "recipe_version_number",
            "production_line_code",
            "components",
            "created_at",
            "updated_at",
        )

    def get_recipe_code(self, obj):
        return obj.recipe_version.recipe.code if obj.recipe_version_id else None

    def get_recipe_version_number(self, obj):
        return obj.recipe_version.version_number if obj.recipe_version_id else None

    def get_production_line_code(self, obj):
        return obj.production_line.code if obj.production_line_id else None


# ─── Feed batches (read-only) ────────────────────────────────────────────


class FeedBatchSerializer(serializers.ModelSerializer):
    recipe_code = serializers.SerializerMethodField()
    storage_bin_code = serializers.SerializerMethodField()
    task_doc_number = serializers.SerializerMethodField()

    class Meta:
        model = FeedBatch
        fields = (
            "id",
            "doc_number",
            "module",
            "produced_by_task",
            "recipe_version",
            "produced_at",
            "quantity_kg",
            "current_quantity_kg",
            "unit_cost_uzs",
            "total_cost_uzs",
            "storage_bin",
            "storage_warehouse",
            "status",
            "is_medicated",
            "withdrawal_period_days",
            "withdrawal_period_ends",
            "quality_passport_status",
            "notes",
            "recipe_code",
            "storage_bin_code",
            "task_doc_number",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields  # создаётся только через сервис

    def get_recipe_code(self, obj):
        if not obj.recipe_version_id:
            return None
        return obj.recipe_version.recipe.code

    def get_storage_bin_code(self, obj):
        return obj.storage_bin.code if obj.storage_bin_id else None

    def get_task_doc_number(self, obj):
        return obj.produced_by_task.doc_number if obj.produced_by_task_id else None
