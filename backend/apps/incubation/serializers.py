from datetime import date as date_type
from decimal import Decimal

from rest_framework import serializers

from .models import IncubationRegimeDay, IncubationRun, MirageInspection


class IncubationRunSerializer(serializers.ModelSerializer):
    incubator_block_code = serializers.SerializerMethodField()
    hatcher_block_code = serializers.SerializerMethodField()
    batch_doc = serializers.SerializerMethodField()
    # Computed — actual days since loaded_date (клампится в [0..days_total]).
    # Поле current_day в БД deprecated, но остаётся для back-compat.
    current_day = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    hatchability_pct = serializers.SerializerMethodField()
    mortality_pct = serializers.SerializerMethodField()

    class Meta:
        model = IncubationRun
        fields = (
            "id",
            "doc_number",
            "module",
            "incubator_block",
            "hatcher_block",
            "batch",
            "loaded_date",
            "expected_hatch_date",
            "actual_hatch_date",
            "eggs_loaded",
            "eggs_broken_on_load",
            "fertile_eggs",
            "hatched_count",
            "discarded_count",
            "days_total",
            "current_day",
            "days_remaining",
            "hatchability_pct",
            "mortality_pct",
            "status",
            "technologist",
            "notes",
            "incubator_block_code",
            "hatcher_block_code",
            "batch_doc",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",  # меняется только через hatch action
            "actual_hatch_date",
            "hatched_count",
            "current_day",
            "days_remaining",
            "hatchability_pct",
            "mortality_pct",
            "incubator_block_code",
            "hatcher_block_code",
            "batch_doc",
            "created_at",
            "updated_at",
        )

    def get_incubator_block_code(self, obj):
        return obj.incubator_block.code if obj.incubator_block_id else None

    def get_hatcher_block_code(self, obj):
        return obj.hatcher_block.code if obj.hatcher_block_id else None

    def get_batch_doc(self, obj):
        return obj.batch.doc_number if obj.batch_id else None

    def get_current_day(self, obj) -> int:
        """День инкубации от loaded_date (0..days_total). Для TRANSFERRED — фикс на actual_hatch_date."""
        total = obj.days_total or 21
        if not obj.loaded_date:
            return 0
        if obj.status == IncubationRun.Status.TRANSFERRED and obj.actual_hatch_date:
            days = (obj.actual_hatch_date - obj.loaded_date).days
            return max(0, min(days, total))
        if obj.status == IncubationRun.Status.CANCELLED:
            return 0
        delta = (date_type.today() - obj.loaded_date).days
        return max(0, min(delta, total))

    def get_days_remaining(self, obj) -> int:
        total = obj.days_total or 21
        return max(0, total - self.get_current_day(obj))

    def get_hatchability_pct(self, obj):
        """hatched / fertile × 100. None если нет fertile_eggs или вывод не сделан."""
        if not obj.fertile_eggs:
            return None
        if obj.hatched_count is None:
            return None
        pct = (Decimal(obj.hatched_count) / Decimal(obj.fertile_eggs) * Decimal("100")).quantize(Decimal("0.01"))
        return str(pct)

    def get_mortality_pct(self, obj):
        """(discarded + эмбриональная смертность) / eggs_loaded × 100."""
        if not obj.eggs_loaded:
            return None
        discarded = obj.discarded_count or 0
        additional = 0
        if (
            obj.status == IncubationRun.Status.TRANSFERRED
            and obj.fertile_eggs is not None
            and obj.hatched_count is not None
            and obj.fertile_eggs > obj.hatched_count
        ):
            additional = obj.fertile_eggs - obj.hatched_count
        total_bad = discarded + additional
        pct = (Decimal(total_bad) / Decimal(obj.eggs_loaded) * Decimal("100")).quantize(Decimal("0.01"))
        return str(pct)


class IncubationRegimeDaySerializer(serializers.ModelSerializer):
    observed_by_name = serializers.CharField(
        source="observed_by.full_name", read_only=True, default=None, allow_null=True,
    )

    class Meta:
        model = IncubationRegimeDay
        fields = (
            "id",
            "run",
            "day",
            "temperature_c",
            "humidity_percent",
            "egg_turns_per_day",
            "actual_temperature_c",
            "actual_humidity_percent",
            "observed_at",
            "observed_by",
            "observed_by_name",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "observed_by_name", "created_at")

    def validate(self, attrs):
        run = attrs.get("run") or (self.instance.run if self.instance else None)
        day = attrs.get("day") or (self.instance.day if self.instance else None)
        if run and day is not None:
            total = run.days_total or 21
            if day < 1 or day > total:
                raise serializers.ValidationError(
                    {"day": f"День должен быть в диапазоне 1..{total}."}
                )
            qs = IncubationRegimeDay.objects.filter(run=run, day=day)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"day": f"Замер за день {day} уже существует."}
                )
        return attrs


class MirageInspectionSerializer(serializers.ModelSerializer):
    inspector_name = serializers.CharField(
        source="inspector.full_name", read_only=True, default=None, allow_null=True,
    )
    infertile_pct = serializers.SerializerMethodField()

    class Meta:
        model = MirageInspection
        fields = (
            "id",
            "run",
            "inspection_date",
            "day_of_incubation",
            "inspected_count",
            "fertile_count",
            "discarded_count",
            "inspector",
            "inspector_name",
            "notes",
            "infertile_pct",
            "created_at",
        )
        read_only_fields = ("id", "inspector_name", "infertile_pct", "created_at")

    def get_infertile_pct(self, obj):
        if not obj.inspected_count:
            return None
        infertile = obj.inspected_count - obj.fertile_count
        pct = (Decimal(infertile) / Decimal(obj.inspected_count) * Decimal("100")).quantize(Decimal("0.01"))
        return str(pct)

    def validate(self, attrs):
        run = attrs.get("run") or (self.instance.run if self.instance else None)
        insp_date = attrs.get("inspection_date") or (
            self.instance.inspection_date if self.instance else None
        )
        inspected = attrs.get("inspected_count")
        fertile = attrs.get("fertile_count")
        discarded = attrs.get("discarded_count", 0)

        if run and insp_date:
            qs = MirageInspection.objects.filter(run=run, inspection_date=insp_date)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"inspection_date": f"Овоскопия за {insp_date} уже проведена."}
                )

        if inspected is not None and run and inspected > run.eggs_loaded:
            raise serializers.ValidationError(
                {"inspected_count": (
                    f"Осмотрено ({inspected}) больше чем загружено ({run.eggs_loaded})."
                )}
            )
        if (
            inspected is not None
            and fertile is not None
            and discarded is not None
            and (fertile + discarded) > inspected
        ):
            raise serializers.ValidationError(
                "Сумма оплодотворённых и отбракованных не может превышать осмотренных."
            )
        return attrs
