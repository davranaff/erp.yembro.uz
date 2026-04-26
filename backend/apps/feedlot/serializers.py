from decimal import Decimal

from rest_framework import serializers

from .models import (
    DailyWeighing,
    FeedlotBatch,
    FeedlotFeedConsumption,
    FeedlotMortality,
)


class FeedlotBatchSerializer(serializers.ModelSerializer):
    house_code = serializers.SerializerMethodField()
    batch_doc = serializers.SerializerMethodField()
    # Computed KPI (read-only)
    days_on_feedlot = serializers.SerializerMethodField()
    survival_pct = serializers.SerializerMethodField()
    total_mortality_pct = serializers.SerializerMethodField()
    current_avg_weight_kg = serializers.SerializerMethodField()
    total_feed_kg = serializers.SerializerMethodField()
    total_gain_kg = serializers.SerializerMethodField()
    total_fcr = serializers.SerializerMethodField()

    class Meta:
        model = FeedlotBatch
        fields = (
            "id",
            "doc_number",
            "module",
            "house_block",
            "batch",
            "placed_date",
            "target_slaughter_date",
            "target_weight_kg",
            "initial_heads",
            "current_heads",
            "status",
            "technologist",
            "notes",
            "house_code",
            "batch_doc",
            "days_on_feedlot",
            "survival_pct",
            "total_mortality_pct",
            "current_avg_weight_kg",
            "total_feed_kg",
            "total_gain_kg",
            "total_fcr",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "house_code",
            "batch_doc",
            "days_on_feedlot",
            "survival_pct",
            "total_mortality_pct",
            "current_avg_weight_kg",
            "total_feed_kg",
            "total_gain_kg",
            "total_fcr",
            "created_at",
            "updated_at",
        )

    def get_house_code(self, obj):
        return obj.house_block.code if obj.house_block_id else None

    def get_batch_doc(self, obj):
        return obj.batch.doc_number if obj.batch_id else None

    def _kpi(self, obj):
        """Lazy-cache KPI на инстансе сериализатора per-object."""
        cache = getattr(self, "_kpi_cache", None)
        if cache is None:
            cache = {}
            self._kpi_cache = cache
        if obj.id not in cache:
            from .services.fcr import get_kpi
            cache[obj.id] = get_kpi(obj)
        return cache[obj.id]

    def get_days_on_feedlot(self, obj):
        return self._kpi(obj).days_on_feedlot

    def get_survival_pct(self, obj):
        return str(self._kpi(obj).survival_pct)

    def get_total_mortality_pct(self, obj):
        return str(self._kpi(obj).total_mortality_pct)

    def get_current_avg_weight_kg(self, obj):
        v = self._kpi(obj).current_avg_weight_kg
        return str(v) if v is not None else None

    def get_total_feed_kg(self, obj):
        return str(self._kpi(obj).total_feed_kg)

    def get_total_gain_kg(self, obj):
        return str(self._kpi(obj).total_gain_kg)

    def get_total_fcr(self, obj):
        v = self._kpi(obj).total_fcr
        return str(v) if v is not None else None


class DailyWeighingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyWeighing
        fields = (
            "id",
            "feedlot_batch",
            "date",
            "day_of_age",
            "sample_size",
            "avg_weight_kg",
            "gain_kg",
            "operator",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "gain_kg", "created_at")


class FeedlotFeedConsumptionSerializer(serializers.ModelSerializer):
    feed_batch_doc = serializers.SerializerMethodField()

    class Meta:
        model = FeedlotFeedConsumption
        fields = (
            "id",
            "feedlot_batch",
            "period_from_day",
            "period_to_day",
            "feed_type",
            "feed_batch",
            "feed_batch_doc",
            "total_kg",
            "per_head_g",
            "period_fcr",
            "notes",
            "created_at",
        )
        read_only_fields = (
            "id",
            "feed_batch_doc",
            "per_head_g",
            "period_fcr",
            "created_at",
        )

    def get_feed_batch_doc(self, obj):
        return obj.feed_batch.doc_number if obj.feed_batch_id else None


class FeedlotMortalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedlotMortality
        fields = (
            "id",
            "feedlot_batch",
            "date",
            "day_of_age",
            "dead_count",
            "cause",
            "notes",
            "recorded_by",
            "created_at",
        )
        read_only_fields = ("id", "created_at")
