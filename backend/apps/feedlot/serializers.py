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

    def validate_sample_size(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Размер выборки должен быть больше нуля.")
        return value

    def validate_avg_weight_kg(self, value):
        if value is None or Decimal(value) <= 0:
            raise serializers.ValidationError("Средний вес должен быть больше нуля.")
        return value

    def validate(self, attrs):
        # day_of_age должен быть в пределах разумного: 0 ≤ day ≤ today−placed_date+30
        # (запас 30 дней для записи задним числом — гибкость, но без откровенных опечаток)
        from datetime import date as _date

        batch = attrs.get("feedlot_batch") or getattr(self.instance, "feedlot_batch", None)
        day = attrs.get("day_of_age", getattr(self.instance, "day_of_age", None))
        if batch and day is not None:
            max_day = (_date.today() - batch.placed_date).days + 30
            if day < 0 or day > max_day:
                raise serializers.ValidationError(
                    {"day_of_age": (
                        f"День откорма должен быть в [0; {max_day}] "
                        f"(партия посажена {batch.placed_date})."
                    )},
                )
        return attrs


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

    def validate_total_kg(self, value):
        if value is None or Decimal(value) <= 0:
            raise serializers.ValidationError("Количество должно быть больше нуля.")
        return value

    def validate(self, attrs):
        # period_to_day >= period_from_day
        from_day = attrs.get(
            "period_from_day", getattr(self.instance, "period_from_day", None),
        )
        to_day = attrs.get(
            "period_to_day", getattr(self.instance, "period_to_day", None),
        )
        if from_day is not None and to_day is not None and to_day < from_day:
            raise serializers.ValidationError(
                {"period_to_day": "Конец периода не может быть раньше его начала."},
            )

        # total_kg ≤ остаток в партии корма (если партия задана)
        feed_batch = attrs.get("feed_batch", getattr(self.instance, "feed_batch", None))
        total_kg = attrs.get("total_kg", getattr(self.instance, "total_kg", None))
        if feed_batch and total_kg is not None:
            available = Decimal(feed_batch.current_quantity_kg or 0)
            if Decimal(total_kg) > available:
                raise serializers.ValidationError(
                    {"total_kg": (
                        f"Недостаточно остатка в партии корма "
                        f"{feed_batch.doc_number}: доступно {available} кг, "
                        f"запрошено {total_kg} кг."
                    )},
                )
        return attrs


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

    def validate_dead_count(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Должно быть больше нуля.")
        return value

    def validate(self, attrs):
        batch = attrs.get(
            "feedlot_batch", getattr(self.instance, "feedlot_batch", None),
        )
        dead = attrs.get("dead_count", getattr(self.instance, "dead_count", None))
        if batch and dead is not None:
            # При обновлении существующей записи — игнорируем её собственный dead_count
            # из проверки превышения (она уже была учтена в current_heads).
            already = self.instance.dead_count if self.instance else 0
            if dead - already > (batch.current_heads or 0):
                raise serializers.ValidationError(
                    {"dead_count": (
                        f"Падёж {dead} превышает текущее поголовье "
                        f"{batch.current_heads} в партии {batch.doc_number}."
                    )},
                )
        # date не должна быть до placed_date или позже сегодняшнего
        date_value = attrs.get("date", getattr(self.instance, "date", None))
        if batch and date_value:
            if date_value < batch.placed_date:
                raise serializers.ValidationError(
                    {"date": (
                        f"Дата падежа раньше даты посадки партии "
                        f"({batch.placed_date})."
                    )},
                )
        return attrs
