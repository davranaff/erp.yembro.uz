from rest_framework import serializers

from .models import InterModuleTransfer


class InterModuleTransferSerializer(serializers.ModelSerializer):
    from_module_code = serializers.SerializerMethodField()
    from_module_name = serializers.SerializerMethodField()
    to_module_code = serializers.SerializerMethodField()
    to_module_name = serializers.SerializerMethodField()
    from_block_code = serializers.SerializerMethodField()
    to_block_code = serializers.SerializerMethodField()
    from_warehouse_code = serializers.SerializerMethodField()
    to_warehouse_code = serializers.SerializerMethodField()
    nomenclature_sku = serializers.SerializerMethodField()
    nomenclature_name = serializers.SerializerMethodField()
    unit_code = serializers.SerializerMethodField()
    batch_doc_number = serializers.SerializerMethodField()
    feed_batch_doc_number = serializers.SerializerMethodField()

    # doc_number авто-генерируется при accept
    doc_number = serializers.CharField(
        max_length=32, required=False, allow_blank=True
    )

    class Meta:
        model = InterModuleTransfer
        fields = (
            "id",
            "doc_number",
            "transfer_date",
            "from_module",
            "to_module",
            "from_block",
            "to_block",
            "from_warehouse",
            "to_warehouse",
            "nomenclature",
            "unit",
            "quantity",
            "cost_uzs",
            "batch",
            "feed_batch",
            "state",
            "review_reason",
            "journal_sender",
            "journal_receiver",
            "stock_outgoing",
            "stock_incoming",
            "posted_at",
            "notes",
            # displays:
            "from_module_code",
            "from_module_name",
            "to_module_code",
            "to_module_name",
            "from_block_code",
            "to_block_code",
            "from_warehouse_code",
            "to_warehouse_code",
            "nomenclature_sku",
            "nomenclature_name",
            "unit_code",
            "batch_doc_number",
            "feed_batch_doc_number",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "state",
            "journal_sender",
            "journal_receiver",
            "stock_outgoing",
            "stock_incoming",
            "posted_at",
            "from_module_code",
            "from_module_name",
            "to_module_code",
            "to_module_name",
            "from_block_code",
            "to_block_code",
            "from_warehouse_code",
            "to_warehouse_code",
            "nomenclature_sku",
            "nomenclature_name",
            "unit_code",
            "batch_doc_number",
            "feed_batch_doc_number",
            "created_at",
            "updated_at",
        )

    def get_from_module_code(self, obj):
        return obj.from_module.code if obj.from_module_id else None

    def get_from_module_name(self, obj):
        return obj.from_module.name if obj.from_module_id else None

    def get_to_module_code(self, obj):
        return obj.to_module.code if obj.to_module_id else None

    def get_to_module_name(self, obj):
        return obj.to_module.name if obj.to_module_id else None

    def get_from_block_code(self, obj):
        return obj.from_block.code if obj.from_block_id else None

    def get_to_block_code(self, obj):
        return obj.to_block.code if obj.to_block_id else None

    def get_from_warehouse_code(self, obj):
        return obj.from_warehouse.code if obj.from_warehouse_id else None

    def get_to_warehouse_code(self, obj):
        return obj.to_warehouse.code if obj.to_warehouse_id else None

    def get_nomenclature_sku(self, obj):
        return obj.nomenclature.sku if obj.nomenclature_id else None

    def get_nomenclature_name(self, obj):
        return obj.nomenclature.name if obj.nomenclature_id else None

    def get_unit_code(self, obj):
        return obj.unit.code if obj.unit_id else None

    def get_batch_doc_number(self, obj):
        return obj.batch.doc_number if obj.batch_id else None

    def get_feed_batch_doc_number(self, obj):
        return obj.feed_batch.doc_number if obj.feed_batch_id else None

    def validate(self, attrs):
        if self.instance and self.instance.state != InterModuleTransfer.State.DRAFT:
            raise serializers.ValidationError(
                {"state": "Редактирование возможно только в DRAFT."}
            )
        return attrs
