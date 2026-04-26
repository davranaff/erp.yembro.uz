from datetime import date as date_type

from rest_framework import serializers

from .models import (
    BreedingFeedConsumption,
    BreedingHerd,
    BreedingMortality,
    DailyEggProduction,
)


class BreedingHerdSerializer(serializers.ModelSerializer):
    block_code = serializers.SerializerMethodField()
    # Computed: возраст считается на лету от placed_at + возраст при посадке.
    # Колонка БД `current_age_weeks` больше не используется, но оставлена для
    # обратной совместимости (deprecated).
    current_age_weeks = serializers.SerializerMethodField()

    class Meta:
        model = BreedingHerd
        fields = (
            "id",
            "doc_number",
            "module",
            "block",
            "direction",
            "source_counterparty",
            "source_batch",
            "placed_at",
            "initial_heads",
            "current_heads",
            "age_weeks_at_placement",
            "current_age_weeks",
            "status",
            "technologist",
            "notes",
            "block_code",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id", "block_code", "current_age_weeks", "created_at", "updated_at",
        )

    def get_block_code(self, obj):
        return obj.block.code if obj.block_id else None

    def get_current_age_weeks(self, obj):
        """Фактический возраст на сегодня: age_at_placement + недели с posадки."""
        if not obj.placed_at:
            return obj.age_weeks_at_placement
        delta_days = (date_type.today() - obj.placed_at).days
        if delta_days < 0:
            delta_days = 0
        return (obj.age_weeks_at_placement or 0) + (delta_days // 7)


class DailyEggProductionSerializer(serializers.ModelSerializer):
    herd_doc = serializers.SerializerMethodField()

    class Meta:
        model = DailyEggProduction
        fields = (
            "id",
            "herd",
            "date",
            "eggs_collected",
            "unfit_eggs",
            "outgoing_batch",
            "notes",
            "herd_doc",
            "created_at",
        )
        read_only_fields = ("id", "herd_doc", "created_at")

    def get_herd_doc(self, obj):
        return obj.herd.doc_number if obj.herd_id else None

    def validate(self, attrs):
        herd = attrs.get("herd") or (self.instance.herd if self.instance else None)
        date = attrs.get("date") or (self.instance.date if self.instance else None)
        if herd and date:
            qs = DailyEggProduction.objects.filter(herd=herd, date=date)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"date": "За эту дату уже есть запись яйцесбора для этого стада."}
                )
        return attrs


class BreedingMortalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = BreedingMortality
        fields = (
            "id",
            "herd",
            "date",
            "dead_count",
            "cause",
            "notes",
            "recorded_by",
            "created_at",
        )
        read_only_fields = ("id", "recorded_by", "created_at")

    def validate(self, attrs):
        herd = attrs.get("herd") or (self.instance.herd if self.instance else None)
        date = attrs.get("date") or (self.instance.date if self.instance else None)
        if herd and date:
            qs = BreedingMortality.objects.filter(herd=herd, date=date)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"date": "За эту дату уже есть запись падежа. Используйте кнопку «Снятие» для дополнения."}
                )
        return attrs


class BreedingFeedConsumptionSerializer(serializers.ModelSerializer):
    feed_batch_doc = serializers.SerializerMethodField()
    feed_batch_recipe = serializers.SerializerMethodField()
    unit_cost_uzs = serializers.SerializerMethodField()
    total_cost_uzs = serializers.SerializerMethodField()

    class Meta:
        model = BreedingFeedConsumption
        fields = (
            "id",
            "herd",
            "date",
            "feed_batch",
            "feed_batch_doc",
            "feed_batch_recipe",
            "unit_cost_uzs",
            "total_cost_uzs",
            "quantity_kg",
            "per_head_g",
            "notes",
            "created_at",
        )
        read_only_fields = (
            "id", "feed_batch_doc", "feed_batch_recipe",
            "unit_cost_uzs", "total_cost_uzs", "created_at",
        )

    def get_feed_batch_doc(self, obj):
        return obj.feed_batch.doc_number if obj.feed_batch_id else None

    def get_feed_batch_recipe(self, obj):
        if not obj.feed_batch_id or not obj.feed_batch.recipe_version_id:
            return None
        return obj.feed_batch.recipe_version.recipe.code

    def get_unit_cost_uzs(self, obj):
        return str(obj.feed_batch.unit_cost_uzs) if obj.feed_batch_id else None

    def get_total_cost_uzs(self, obj):
        if not obj.feed_batch_id or obj.quantity_kg is None:
            return None
        return str(obj.quantity_kg * obj.feed_batch.unit_cost_uzs)
