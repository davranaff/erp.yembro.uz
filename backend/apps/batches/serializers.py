from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from .models import Batch, BatchChainStep, BatchCostEntry


class BatchCostEntrySerializer(serializers.ModelSerializer):
    module_code = serializers.SerializerMethodField()

    class Meta:
        model = BatchCostEntry
        fields = (
            "id",
            "batch",
            "category",
            "amount_uzs",
            "description",
            "occurred_at",
            "module",
            "module_code",
            "source_content_type",
            "source_object_id",
            "created_at",
        )
        read_only_fields = fields

    def get_module_code(self, obj):
        return obj.module.code if obj.module_id else None


class BatchChainStepSerializer(serializers.ModelSerializer):
    module_code = serializers.SerializerMethodField()
    block_code = serializers.SerializerMethodField()
    transfer_in_doc = serializers.SerializerMethodField()
    transfer_out_doc = serializers.SerializerMethodField()

    class Meta:
        model = BatchChainStep
        fields = (
            "id",
            "batch",
            "sequence",
            "module",
            "block",
            "entered_at",
            "exited_at",
            "quantity_in",
            "quantity_out",
            "accumulated_cost_at_exit",
            "transfer_in",
            "transfer_out",
            "note",
            "module_code",
            "block_code",
            "transfer_in_doc",
            "transfer_out_doc",
        )
        read_only_fields = fields

    def get_module_code(self, obj):
        return obj.module.code if obj.module_id else None

    def get_block_code(self, obj):
        return obj.block.code if obj.block_id else None

    def get_transfer_in_doc(self, obj):
        return obj.transfer_in.doc_number if obj.transfer_in_id else None

    def get_transfer_out_doc(self, obj):
        return obj.transfer_out.doc_number if obj.transfer_out_id else None


class BatchSerializer(serializers.ModelSerializer):
    nomenclature_sku = serializers.SerializerMethodField()
    nomenclature_name = serializers.SerializerMethodField()
    unit_code = serializers.SerializerMethodField()
    current_module_code = serializers.SerializerMethodField()
    current_block_code = serializers.SerializerMethodField()
    origin_module_code = serializers.SerializerMethodField()
    parent_doc_number = serializers.SerializerMethodField()
    reserved_quantity = serializers.SerializerMethodField()
    available_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Batch
        fields = (
            "id",
            "doc_number",
            "nomenclature",
            "unit",
            "origin_module",
            "current_module",
            "current_block",
            "current_quantity",
            "initial_quantity",
            "reserved_quantity",
            "available_quantity",
            "accumulated_cost_uzs",
            "state",
            "started_at",
            "completed_at",
            "withdrawal_period_ends",
            "parent_batch",
            "origin_purchase",
            "origin_counterparty",
            "notes",
            "nomenclature_sku",
            "nomenclature_name",
            "unit_code",
            "current_module_code",
            "current_block_code",
            "origin_module_code",
            "parent_doc_number",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields  # партии создаются только сервисами

    def get_nomenclature_sku(self, obj):
        return obj.nomenclature.sku if obj.nomenclature_id else None

    def get_nomenclature_name(self, obj):
        return obj.nomenclature.name if obj.nomenclature_id else None

    def get_unit_code(self, obj):
        return obj.unit.code if obj.unit_id else None

    def get_current_module_code(self, obj):
        return obj.current_module.code if obj.current_module_id else None

    def get_current_block_code(self, obj):
        return obj.current_block.code if obj.current_block_id else None

    def get_origin_module_code(self, obj):
        return obj.origin_module.code if obj.origin_module_id else None

    def get_parent_doc_number(self, obj):
        return obj.parent_batch.doc_number if obj.parent_batch_id else None

    def _reserved_in_drafts(self, obj) -> Decimal:
        """
        Сколько единиц партии «зарезервировано» в DRAFT-продажах.

        Считаем сумму quantity по всем SaleItem чьи order.status=DRAFT
        и order.organization=organization. Это not-yet-listed reservation:
        пока продажа не проведена, остаток батча не уменьшается, но другая
        продажа уже не должна это количество перепродать.
        """
        from apps.sales.models import SaleItem, SaleOrder

        agg = SaleItem.objects.filter(
            batch_id=obj.id,
            order__status=SaleOrder.Status.DRAFT,
        ).aggregate(s=Sum("quantity"))
        return Decimal(agg["s"] or 0)

    def get_reserved_quantity(self, obj):
        return str(self._reserved_in_drafts(obj))

    def get_available_quantity(self, obj):
        """current_quantity − зарезервированное в DRAFT-продажах. Не меньше 0."""
        cur = Decimal(obj.current_quantity or 0)
        reserved = self._reserved_in_drafts(obj)
        avail = cur - reserved
        if avail < 0:
            avail = Decimal("0")
        return str(avail)
