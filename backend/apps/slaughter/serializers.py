from rest_framework import serializers

from .models import (
    SlaughterLabTest,
    SlaughterQualityCheck,
    SlaughterShift,
    SlaughterYield,
)


class SlaughterShiftSerializer(serializers.ModelSerializer):
    line_code = serializers.SerializerMethodField()
    batch_doc = serializers.SerializerMethodField()
    # Computed KPI (read-only)
    total_output_kg = serializers.SerializerMethodField()
    total_output_pct = serializers.SerializerMethodField()
    waste_kg = serializers.SerializerMethodField()
    waste_pct = serializers.SerializerMethodField()
    carcass_kg = serializers.SerializerMethodField()
    carcass_yield_pct = serializers.SerializerMethodField()
    yield_per_head_kg = serializers.SerializerMethodField()
    defect_rate = serializers.SerializerMethodField()
    quality_checked = serializers.SerializerMethodField()
    yields_count = serializers.SerializerMethodField()
    lab_pending_count = serializers.SerializerMethodField()
    lab_passed_count = serializers.SerializerMethodField()
    lab_failed_count = serializers.SerializerMethodField()

    class Meta:
        model = SlaughterShift
        fields = (
            "id",
            "doc_number",
            "module",
            "line_block",
            "source_batch",
            "shift_date",
            "start_time",
            "end_time",
            "live_heads_received",
            "live_weight_kg_total",
            "status",
            "foreman",
            "notes",
            "line_code",
            "batch_doc",
            "total_output_kg",
            "total_output_pct",
            "waste_kg",
            "waste_pct",
            "carcass_kg",
            "carcass_yield_pct",
            "yield_per_head_kg",
            "defect_rate",
            "quality_checked",
            "yields_count",
            "lab_pending_count",
            "lab_passed_count",
            "lab_failed_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",  # меняется только через post_shift action
            "end_time",
            "line_code",
            "batch_doc",
            "total_output_kg",
            "total_output_pct",
            "waste_kg",
            "waste_pct",
            "carcass_kg",
            "carcass_yield_pct",
            "yield_per_head_kg",
            "defect_rate",
            "quality_checked",
            "yields_count",
            "lab_pending_count",
            "lab_passed_count",
            "lab_failed_count",
            "created_at",
            "updated_at",
        )

    def get_line_code(self, obj):
        return obj.line_block.code if obj.line_block_id else None

    def get_batch_doc(self, obj):
        return obj.source_batch.doc_number if obj.source_batch_id else None

    def _kpi(self, obj):
        """Lazy-cache KPI на инстансе сериализатора per-object."""
        cache = getattr(self, "_kpi_cache", None)
        if cache is None:
            cache = {}
            self._kpi_cache = cache
        if obj.id not in cache:
            from .services.stats import get_shift_kpi

            cache[obj.id] = get_shift_kpi(obj)
        return cache[obj.id]

    def get_total_output_kg(self, obj):
        return str(self._kpi(obj).total_output_kg)

    def get_total_output_pct(self, obj):
        v = self._kpi(obj).total_output_pct
        return str(v) if v is not None else None

    def get_waste_kg(self, obj):
        v = self._kpi(obj).waste_kg
        return str(v) if v is not None else None

    def get_waste_pct(self, obj):
        v = self._kpi(obj).waste_pct
        return str(v) if v is not None else None

    def get_carcass_kg(self, obj):
        return str(self._kpi(obj).carcass_kg)

    def get_carcass_yield_pct(self, obj):
        v = self._kpi(obj).carcass_yield_pct
        return str(v) if v is not None else None

    def get_yield_per_head_kg(self, obj):
        v = self._kpi(obj).yield_per_head_kg
        return str(v) if v is not None else None

    def get_defect_rate(self, obj):
        v = self._kpi(obj).defect_rate
        return str(v) if v is not None else None

    def get_quality_checked(self, obj):
        return self._kpi(obj).quality_checked

    def get_yields_count(self, obj):
        return self._kpi(obj).yields_count

    def get_lab_pending_count(self, obj):
        return self._kpi(obj).lab_pending_count

    def get_lab_passed_count(self, obj):
        return self._kpi(obj).lab_passed_count

    def get_lab_failed_count(self, obj):
        return self._kpi(obj).lab_failed_count


class SlaughterYieldSerializer(serializers.ModelSerializer):
    nom_sku = serializers.SerializerMethodField()
    nom_name = serializers.SerializerMethodField()
    unit_code = serializers.SerializerMethodField()
    output_batch_doc = serializers.SerializerMethodField()
    yield_pct = serializers.SerializerMethodField()
    norm_pct = serializers.SerializerMethodField()
    deviation_pct = serializers.SerializerMethodField()
    is_within_tolerance = serializers.SerializerMethodField()

    class Meta:
        model = SlaughterYield
        fields = (
            "id",
            "shift",
            "nomenclature",
            "grade",
            "quantity",
            "unit",
            "share_percent",
            "output_batch",
            "notes",
            "nom_sku",
            "nom_name",
            "unit_code",
            "output_batch_doc",
            "yield_pct",
            "norm_pct",
            "deviation_pct",
            "is_within_tolerance",
            "created_at",
        )
        read_only_fields = (
            "id",
            "nom_sku",
            "nom_name",
            "unit_code",
            "output_batch_doc",
            "yield_pct",
            "norm_pct",
            "deviation_pct",
            "is_within_tolerance",
            "created_at",
        )

    def get_nom_sku(self, obj):
        return obj.nomenclature.sku if obj.nomenclature_id else None

    def get_nom_name(self, obj):
        return obj.nomenclature.name if obj.nomenclature_id else None

    def get_unit_code(self, obj):
        return obj.unit.code if obj.unit_id else None

    def get_output_batch_doc(self, obj):
        return obj.output_batch.doc_number if obj.output_batch_id else None

    def _yield_metrics(self, obj):
        """Lazy compute yield_pct/norm/deviation для конкретной строки."""
        cache = getattr(self, "_yield_cache", None)
        if cache is None:
            cache = {}
            self._yield_cache = cache
        if obj.id in cache:
            return cache[obj.id]
        from decimal import Decimal

        from .services.stats import (
            BROILER_YIELD_NORMS,
            KG_CODES,
            YIELD_TOLERANCE,
            compute_yield_pct,
        )

        if not obj.unit_id or obj.unit.code.lower() not in KG_CODES:
            result = (None, None, None, True)
        else:
            live_kg = obj.shift.live_weight_kg_total or Decimal("0")
            yp = compute_yield_pct(obj.quantity, live_kg)
            norm = BROILER_YIELD_NORMS.get(obj.nomenclature.sku.upper())
            if yp is not None and norm is not None:
                dev = (yp - norm).quantize(Decimal("0.01"))
                within = abs(dev) <= YIELD_TOLERANCE
            else:
                dev = None
                within = True
            result = (yp, norm, dev, within)
        cache[obj.id] = result
        return result

    def get_yield_pct(self, obj):
        v = self._yield_metrics(obj)[0]
        return str(v) if v is not None else None

    def get_norm_pct(self, obj):
        v = self._yield_metrics(obj)[1]
        return str(v) if v is not None else None

    def get_deviation_pct(self, obj):
        v = self._yield_metrics(obj)[2]
        return str(v) if v is not None else None

    def get_is_within_tolerance(self, obj):
        return self._yield_metrics(obj)[3]

    def validate(self, attrs):
        """Сумма выходов в кг не должна превышать живой вес смены."""
        from decimal import Decimal

        from .services.stats import KG_CODES

        attrs = super().validate(attrs)
        shift = attrs.get("shift") or (self.instance.shift if self.instance else None)
        unit = attrs.get("unit") or (self.instance.unit if self.instance else None)
        quantity = attrs.get("quantity")
        if quantity is None and self.instance is not None:
            quantity = self.instance.quantity
        if shift is None or unit is None or quantity is None:
            return attrs
        # Только для kg-выходов
        if unit.code.lower() not in KG_CODES:
            return attrs
        live_kg = shift.live_weight_kg_total or Decimal("0")
        if live_kg <= 0:
            return attrs
        # Сумма других kg-выходов в этой смене (исключая редактируемый)
        existing_qs = shift.yields.select_related("unit").exclude(
            id=self.instance.id if self.instance else None
        )
        existing_kg = sum(
            (
                y.quantity
                for y in existing_qs
                if y.unit and y.unit.code.lower() in KG_CODES
            ),
            Decimal("0"),
        )
        new_total = existing_kg + quantity
        if new_total > live_kg:
            already = live_kg - existing_kg
            raise serializers.ValidationError(
                {
                    "quantity": (
                        f"Сумма выходов {new_total} кг превысит живой вес "
                        f"{live_kg} кг. Максимум для этой строки: "
                        f"{already if already > 0 else 0} кг."
                    )
                }
            )
        return attrs


class SlaughterQualityCheckSerializer(serializers.ModelSerializer):
    inspector_name = serializers.SerializerMethodField()

    class Meta:
        model = SlaughterQualityCheck
        fields = (
            "id",
            "shift",
            "carcass_defect_percent",
            "trauma_percent",
            "cooling_temperature_c",
            "confiscation_percent",
            "vet_inspection_passed",
            "inspector",
            "inspector_name",
            "inspected_at",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "inspector_name", "created_at")

    def get_inspector_name(self, obj):
        if not obj.inspector_id:
            return None
        u = obj.inspector
        return (u.get_full_name() if hasattr(u, "get_full_name") else None) or u.email


class SlaughterLabTestSerializer(serializers.ModelSerializer):
    operator_name = serializers.SerializerMethodField()

    class Meta:
        model = SlaughterLabTest
        fields = (
            "id",
            "shift",
            "indicator",
            "normal_range",
            "actual_value",
            "status",
            "sampled_at",
            "result_at",
            "operator",
            "operator_name",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "operator_name", "created_at")

    def get_operator_name(self, obj):
        if not obj.operator_id:
            return None
        u = obj.operator
        return (u.get_full_name() if hasattr(u, "get_full_name") else None) or u.email
