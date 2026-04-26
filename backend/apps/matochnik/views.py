from datetime import date as date_type, timedelta
from decimal import Decimal

from django.db.models import Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.lifecycle import DeleteReasonMixin, ImmutableStatusMixin
from apps.common.viewsets import OrgScopedModelViewSet

from .models import (
    BreedingFeedConsumption,
    BreedingHerd,
    BreedingMortality,
    DailyEggProduction,
)
from .serializers import (
    BreedingFeedConsumptionSerializer,
    BreedingHerdSerializer,
    BreedingMortalitySerializer,
    DailyEggProductionSerializer,
)
from .services.crystallize import EggCrystallizeError, crystallize_egg_batch
from .services.depopulate_herd import HerdDepopulateError, depopulate_herd
from .services.post_feed_consumption import (
    FeedConsumptionPostError,
    post_feed_consumption,
)


class BreedingHerdViewSet(ImmutableStatusMixin, OrgScopedModelViewSet):
    serializer_class = BreedingHerdSerializer
    queryset = BreedingHerd.objects.select_related("block", "technologist")
    module_code = "matochnik"
    immutable_statuses = ("depopulated",)
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["direction", "status", "block"]
    search_fields = ["doc_number", "notes"]
    ordering = ["-placed_at"]

    @action(detail=True, methods=["post"], url_path="crystallize-eggs")
    def crystallize_eggs(self, request, pk=None):
        """POST /api/matochnik/herds/{id}/crystallize-eggs/

        Body: {
            "egg_nomenclature": uuid,
            "date_from": "YYYY-MM-DD",
            "date_to": "YYYY-MM-DD",
            "doc_number": str (optional)
        }
        """
        from apps.nomenclature.models import NomenclatureItem

        herd = self.get_object()
        try:
            nom = NomenclatureItem.objects.get(pk=request.data["egg_nomenclature"])
            df = date_type.fromisoformat(request.data["date_from"])
            dt = date_type.fromisoformat(request.data["date_to"])
        except (KeyError, NomenclatureItem.DoesNotExist, ValueError) as exc:
            raise DRFValidationError({"__all__": f"Некорректные параметры: {exc}"})

        try:
            result = crystallize_egg_batch(
                herd,
                egg_nomenclature=nom,
                date_from=df,
                date_to=dt,
                doc_number=request.data.get("doc_number"),
                user=request.user,
            )
        except EggCrystallizeError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        return Response({
            "batch": {
                "id": str(result.batch.id),
                "doc_number": result.batch.doc_number,
                "quantity": str(result.batch.current_quantity),
            },
            "records_count": result.records_count,
            "total_eggs": result.total_eggs,
        })

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        """
        GET /api/matochnik/herds/{id}/timeline/?days=90

        Единый хронологический таймлайн событий стада:
            - egg         — суточный яйцесбор
            - mortality   — падёж
            - feed        — расход кормов
            - treatment   — вет. обработка
            - crystallize — сформированная партия яиц (из crystallize_egg_batch)
            - move        — перемещение в другой корпус (из audit_log)

        Сортируется по дате (убывание). Для фронта — один List в модалке
        с фильтрами по типу.
        """
        from apps.vet.models import VetTreatmentLog

        herd = self.get_object()
        days = int(request.query_params.get("days", 90))
        today = date_type.today()
        start = today - timedelta(days=days - 1)

        events: list[dict] = []

        # 1. Egg production
        for e in DailyEggProduction.objects.filter(
            herd=herd, date__gte=start, date__lte=today,
        ).select_related("outgoing_batch"):
            clean = (e.eggs_collected or 0) - (e.unfit_eggs or 0)
            events.append({
                "type": "egg",
                "date": e.date.isoformat(),
                "id": str(e.id),
                "title": f"Яйцесбор: {clean} чистых",
                "subtitle": (
                    f"собрано {e.eggs_collected}, брак {e.unfit_eggs}"
                    + (f" · партия {e.outgoing_batch.doc_number}"
                       if e.outgoing_batch_id else "")
                ),
                "notes": e.notes or "",
                "amount": clean,
                "amount_label": "шт",
            })

        # 2. Mortality
        for m in BreedingMortality.objects.filter(
            herd=herd, date__gte=start, date__lte=today,
        ):
            events.append({
                "type": "mortality",
                "date": m.date.isoformat(),
                "id": str(m.id),
                "title": f"Падёж: {m.dead_count} голов",
                "subtitle": m.cause or "",
                "notes": m.notes or "",
                "amount": m.dead_count,
                "amount_label": "гол",
            })

        # 3. Feed consumption
        for f in BreedingFeedConsumption.objects.filter(
            herd=herd, date__gte=start, date__lte=today,
        ).select_related("feed_batch", "feed_batch__recipe_version__recipe"):
            total_cost = None
            if f.feed_batch_id and f.feed_batch.unit_cost_uzs:
                total_cost = f.quantity_kg * f.feed_batch.unit_cost_uzs
            recipe_code = None
            if f.feed_batch_id and f.feed_batch.recipe_version_id:
                recipe_code = f.feed_batch.recipe_version.recipe.code
            events.append({
                "type": "feed",
                "date": f.date.isoformat(),
                "id": str(f.id),
                "title": f"Корм: {f.quantity_kg} кг",
                "subtitle": (
                    f"{f.feed_batch.doc_number}"
                    + (f" · {recipe_code}" if recipe_code else "")
                    if f.feed_batch_id else "без партии"
                ),
                "notes": f.notes or "",
                "amount": str(f.quantity_kg),
                "amount_label": "кг",
                "cost_uzs": str(total_cost) if total_cost is not None else None,
            })

        # 4. Vet treatments
        vet_qs = (
            VetTreatmentLog.objects.filter(
                target_herd=herd,
                treatment_date__gte=start,
                treatment_date__lte=today,
            )
            .select_related(
                "drug", "drug__nomenclature", "stock_batch", "unit",
            )
        )
        for t in vet_qs:
            drug_name = (
                t.drug.nomenclature.name
                if t.drug_id and t.drug.nomenclature_id else "препарат"
            )
            drug_sku = (
                t.drug.nomenclature.sku
                if t.drug_id and t.drug.nomenclature_id else None
            )
            events.append({
                "type": "treatment",
                "date": t.treatment_date.isoformat(),
                "id": str(t.id),
                "title": f"Лечение: {drug_name}",
                "subtitle": (
                    f"{t.dose_quantity} {t.unit.code if t.unit_id else ''} · "
                    f"{t.heads_treated} гол"
                    + (f" · каренция {t.withdrawal_period_days} дн"
                       if t.withdrawal_period_days else "")
                ),
                "notes": t.notes or "",
                "drug_sku": drug_sku,
                "lot_number": t.stock_batch.lot_number if t.stock_batch_id else None,
                "withdrawal_period_days": t.withdrawal_period_days,
                "indication": t.indication or "",
            })

        # 5. Crystallize (создание партии яиц)
        # Распознаём через DailyEggProduction.outgoing_batch: первая дата
        # появления каждого batch в этой связи = дата формирования.
        crystallized_batches: dict = {}
        for e in DailyEggProduction.objects.filter(
            herd=herd, outgoing_batch__isnull=False,
        ).select_related("outgoing_batch"):
            b = e.outgoing_batch
            if b.id in crystallized_batches:
                continue
            crystallized_batches[b.id] = b
        for b in crystallized_batches.values():
            if b.started_at < start or b.started_at > today:
                continue
            events.append({
                "type": "crystallize",
                "date": b.started_at.isoformat(),
                "id": str(b.id),
                "title": f"Сформирована партия {b.doc_number}",
                "subtitle": (
                    f"{b.current_quantity} {b.unit.code if b.unit_id else 'шт'}"
                    f" · {b.state}"
                ),
                "notes": "",
                "batch_doc": b.doc_number,
                "current_module": (
                    b.current_module.code if b.current_module_id else None
                ),
            })

        # Сортировка: по дате убывание, внутри дня — по типу (treatment сверху
        # чтобы каренция была заметна)
        TYPE_PRIORITY = {
            "treatment": 0, "mortality": 1, "crystallize": 2,
            "egg": 3, "feed": 4, "move": 5,
        }
        events.sort(key=lambda ev: (ev["date"], -TYPE_PRIORITY.get(ev["type"], 99)), reverse=True)

        return Response({
            "days": days,
            "from": start.isoformat(),
            "to": today.isoformat(),
            "events": events,
            "counts": {
                "egg": sum(1 for e in events if e["type"] == "egg"),
                "mortality": sum(1 for e in events if e["type"] == "mortality"),
                "feed": sum(1 for e in events if e["type"] == "feed"),
                "treatment": sum(1 for e in events if e["type"] == "treatment"),
                "crystallize": sum(1 for e in events if e["type"] == "crystallize"),
            },
        })

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        """
        GET /api/matochnik/herds/{id}/stats/?days=30

        Сводные метрики стада за окно days (default 30):
            - productivity_avg_pct — яйценоскость, средняя по дням: clean_eggs / current_heads * 100
            - productivity_today_pct — сегодня
            - eggs_total_clean — собрано чистых яиц за окно
            - mortality_total — пало за окно (голов)
            - feed_total_kg — корма за окно (кг)
            - feed_cost_total_uzs — стоимость кормов за окно
            - fcr — feed conversion ratio (кг корма / кг яйца);
              средний вес яйца принят 0.06 кг (бройлерное) / 0.055 (яичное).
            - series — массив дневных точек [{date, eggs_clean, mortality, feed_kg}]
              для sparkline; ровно `days` дней, даже если записей нет.
        """
        herd = self.get_object()
        days = int(request.query_params.get("days", 30))
        today = date_type.today()
        start = today - timedelta(days=days - 1)

        # Все записи в окне
        egg_qs = DailyEggProduction.objects.filter(
            herd=herd, date__gte=start, date__lte=today,
        ).order_by("date")
        mort_qs = BreedingMortality.objects.filter(
            herd=herd, date__gte=start, date__lte=today,
        ).order_by("date")
        feed_qs = BreedingFeedConsumption.objects.filter(
            herd=herd, date__gte=start, date__lte=today,
        ).select_related("feed_batch").order_by("date")

        # Индексы по дате для быстрой сборки серии
        eggs_by_date: dict = {}
        for e in egg_qs:
            clean = (e.eggs_collected or 0) - (e.unfit_eggs or 0)
            eggs_by_date.setdefault(e.date, 0)
            eggs_by_date[e.date] += clean

        mort_by_date: dict = {}
        for m in mort_qs:
            mort_by_date.setdefault(m.date, 0)
            mort_by_date[m.date] += m.dead_count

        feed_kg_by_date: dict = {}
        feed_cost_total = Decimal("0")
        feed_kg_total = Decimal("0")
        for f in feed_qs:
            feed_kg_by_date.setdefault(f.date, Decimal("0"))
            feed_kg_by_date[f.date] += Decimal(f.quantity_kg)
            feed_kg_total += Decimal(f.quantity_kg)
            if f.feed_batch_id and f.feed_batch.unit_cost_uzs:
                feed_cost_total += (
                    Decimal(f.quantity_kg) * Decimal(f.feed_batch.unit_cost_uzs)
                )

        # Серия по дням (all days даже без записей)
        series = []
        eggs_total_clean = 0
        mortality_total = 0
        prod_sum_pct = Decimal("0")
        prod_days_count = 0
        current_heads = herd.current_heads or 0

        for i in range(days):
            d = start + timedelta(days=i)
            eggs = eggs_by_date.get(d, 0)
            mort = mort_by_date.get(d, 0)
            fkg = feed_kg_by_date.get(d, Decimal("0"))
            eggs_total_clean += eggs
            mortality_total += mort
            prod_pct = (
                (Decimal(eggs) / Decimal(current_heads) * Decimal("100"))
                if current_heads > 0 else Decimal("0")
            )
            if eggs > 0:
                prod_sum_pct += prod_pct
                prod_days_count += 1
            series.append({
                "date": d.isoformat(),
                "eggs_clean": eggs,
                "mortality": mort,
                "feed_kg": str(fkg),
            })

        productivity_avg_pct = (
            prod_sum_pct / prod_days_count
            if prod_days_count > 0 else Decimal("0")
        )
        eggs_today = eggs_by_date.get(today, 0)
        productivity_today_pct = (
            Decimal(eggs_today) / Decimal(current_heads) * Decimal("100")
            if current_heads > 0 else Decimal("0")
        )

        # FCR (feed conversion ratio) = feed_kg / egg_mass_kg
        # средний вес яйца: 60 г для бройлерного родительского, 55 г для яичного
        egg_weight_g = 60 if herd.direction == BreedingHerd.Direction.BROILER_PARENT else 55
        egg_mass_kg = (
            Decimal(eggs_total_clean) * Decimal(egg_weight_g) / Decimal("1000")
        )
        fcr = (
            (feed_kg_total / egg_mass_kg).quantize(Decimal("0.01"))
            if egg_mass_kg > 0 else None
        )

        # Активная каренция: максимальная (treatment_date + withdrawal_period_days)
        # из лечений этого стада, если она >= today.
        from apps.vet.models import VetTreatmentLog
        active_withdrawal_until = None
        last_treatments = (
            VetTreatmentLog.objects
            .filter(target_herd=herd, withdrawal_period_days__gt=0)
            .order_by("-treatment_date")[:20]
        )
        for t in last_treatments:
            end = t.treatment_date + timedelta(days=t.withdrawal_period_days)
            if end >= today:
                if active_withdrawal_until is None or end > active_withdrawal_until:
                    active_withdrawal_until = end

        return Response({
            "days": days,
            "from": start.isoformat(),
            "to": today.isoformat(),
            "productivity_avg_pct": str(productivity_avg_pct.quantize(Decimal("0.01"))),
            "productivity_today_pct": str(productivity_today_pct.quantize(Decimal("0.01"))),
            "eggs_total_clean": eggs_total_clean,
            "mortality_total": mortality_total,
            "feed_total_kg": str(feed_kg_total.quantize(Decimal("0.001"))),
            "feed_cost_total_uzs": str(feed_cost_total.quantize(Decimal("0.01"))),
            "fcr": str(fcr) if fcr is not None else None,
            "egg_weight_g": egg_weight_g,
            "active_withdrawal_until": (
                active_withdrawal_until.isoformat()
                if active_withdrawal_until else None
            ),
            "series": series,
        })

    @action(detail=True, methods=["get"], url_path="egg-batches")
    def egg_batches(self, request, pk=None):
        """
        GET /api/matochnik/herds/{id}/egg-batches/

        Партии яиц, сформированные из яйцесбора этого стада (через
        DailyEggProduction.outgoing_batch). Используется в UI (drawer стада).
        """
        from apps.batches.models import Batch
        from apps.batches.serializers import BatchSerializer
        herd = self.get_object()
        batch_ids = (
            DailyEggProduction.objects.filter(
                herd=herd, outgoing_batch__isnull=False,
            )
            .values_list("outgoing_batch_id", flat=True)
            .distinct()
        )
        qs = (
            Batch.objects.filter(pk__in=batch_ids)
            .select_related(
                "nomenclature", "unit", "origin_module",
                "current_module", "current_block",
            )
            .order_by("-started_at")
        )
        return Response(BatchSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        """
        POST /api/matochnik/herds/{id}/move/
        Body: {"block": <uuid>, "reason": str (optional)}

        Переместить стадо в другой корпус (блок). Блок должен принадлежать
        тому же модулю matochnik и той же организации.
        """
        from apps.audit.models import AuditLog
        from apps.audit.services.writer import audit_log
        from apps.warehouses.models import ProductionBlock

        herd = self.get_object()
        try:
            target_block = ProductionBlock.objects.get(pk=request.data["block"])
        except (KeyError, ProductionBlock.DoesNotExist) as exc:
            raise DRFValidationError({"block": f"Блок не найден: {exc}"})

        if target_block.organization_id != herd.organization_id:
            raise DRFValidationError({"block": "Блок из другой организации."})
        if target_block.module_id != herd.module_id:
            raise DRFValidationError({"block": "Блок не принадлежит модулю стада."})
        if target_block.id == herd.block_id:
            raise DRFValidationError({"block": "Стадо уже в этом корпусе."})
        if herd.status == BreedingHerd.Status.DEPOPULATED:
            raise DRFValidationError({"status": "Снятое стадо нельзя перемещать."})

        old_block = herd.block
        reason = request.data.get("reason", "")

        herd.block = target_block
        herd.save(update_fields=["block", "updated_at"])

        audit_log(
            organization=herd.organization,
            module=herd.module,
            actor=request.user,
            action=AuditLog.Action.UPDATE,
            entity=herd,
            action_verb=(
                f"moved herd {herd.doc_number} from {old_block.code} "
                f"to {target_block.code}" + (f" — {reason}" if reason else "")
            ),
        )

        herd.refresh_from_db()
        return Response(self.get_serializer(herd).data)

    @action(detail=True, methods=["post"])
    def depopulate(self, request, pk=None):
        """POST /api/matochnik/herds/{id}/depopulate/
        Body: {
            "reduce_by": int,
            "date": "YYYY-MM-DD" (optional),
            "reason": str (optional),
            "mark_as_mortality": bool (default false)
        }
        """
        herd = self.get_object()
        try:
            reduce_by = int(request.data["reduce_by"])
        except (KeyError, ValueError) as exc:
            raise DRFValidationError(
                {"__all__": f"reduce_by обязателен: {exc}"}
            )
        d = request.data.get("date")
        try:
            date_val = date_type.fromisoformat(d) if d else None
        except ValueError as exc:
            raise DRFValidationError({"date": str(exc)})

        try:
            result = depopulate_herd(
                herd,
                reduce_by=reduce_by,
                date=date_val,
                reason=request.data.get("reason", ""),
                mark_as_mortality=bool(request.data.get("mark_as_mortality", False)),
                user=request.user,
            )
        except HerdDepopulateError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        herd.refresh_from_db()
        data = self.get_serializer(herd).data
        data["_result"] = {
            "current_heads": result.herd.current_heads,
            "status": result.herd.status,
            "mortality_record_id": (
                str(result.mortality_record.id)
                if result.mortality_record else None
            ),
        }
        return Response(data)


class _HerdScopedMixin:
    """
    Общий фикс для child-моделей стада (DailyEggProduction, BreedingMortality,
    BreedingFeedConsumption). У них нет прямого поля `organization` —
    организация определяется через `herd.organization`.

    OrgScopedModelViewSet._save_kwargs_for_create по умолчанию кладёт
    `{organization_field: org}` в serializer.save(), но
    `herd__organization=<...>` — невалидный kwarg для model.objects.create().
    Поэтому возвращаем {} и отдельно валидируем, что herd в той же организации.
    """

    def _save_kwargs_for_create(self, serializer) -> dict:
        # Не подмешиваем organization напрямую — проверка идёт через herd.
        kwargs: dict = {}
        model = serializer.Meta.model if hasattr(serializer, "Meta") else None
        if model is not None:
            field_names = {f.name for f in model._meta.get_fields()}
            if "created_by" in field_names:
                user = getattr(self.request, "user", None)
                if user and getattr(user, "is_authenticated", False):
                    kwargs["created_by"] = user
            # `recorded_by` у BreedingMortality
            if "recorded_by" in field_names:
                user = getattr(self.request, "user", None)
                if user and getattr(user, "is_authenticated", False):
                    kwargs["recorded_by"] = user
        return kwargs

    def perform_create(self, serializer):  # type: ignore[override]
        # Защита: herd должен принадлежать текущей org (которую видит viewset).
        org = getattr(self.request, "organization", None)
        herd = serializer.validated_data.get("herd")
        if org and herd and herd.organization_id != org.id:
            raise DRFValidationError({"herd": "Стадо из другой организации."})
        instance = serializer.save(**self._save_kwargs_for_create(serializer))
        from apps.audit.models import AuditLog
        self._write_audit(AuditLog.Action.CREATE, instance)
        return instance


class DailyEggProductionViewSet(DeleteReasonMixin, _HerdScopedMixin, OrgScopedModelViewSet):
    serializer_class = DailyEggProductionSerializer
    queryset = DailyEggProduction.objects.select_related("herd", "outgoing_batch")
    module_code = "matochnik"
    organization_field = "herd__organization"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["herd", "outgoing_batch"]
    ordering_fields = ["date", "eggs_collected"]
    ordering = ["-date"]


class BreedingMortalityViewSet(DeleteReasonMixin, _HerdScopedMixin, OrgScopedModelViewSet):
    serializer_class = BreedingMortalitySerializer
    queryset = BreedingMortality.objects.select_related("herd")
    module_code = "matochnik"
    organization_field = "herd__organization"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["herd"]
    ordering = ["-date"]


class BreedingFeedConsumptionViewSet(DeleteReasonMixin, _HerdScopedMixin, OrgScopedModelViewSet):
    serializer_class = BreedingFeedConsumptionSerializer
    queryset = BreedingFeedConsumption.objects.select_related("herd", "feed_batch")
    module_code = "matochnik"
    organization_field = "herd__organization"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["herd", "feed_batch"]
    ordering = ["-date"]

    def perform_create(self, serializer):
        """
        При создании BFC сразу проводим списание:
        декремент FeedBatch + проводка Дт 20.01 / Кт 10.05 + BatchCostEntry(FEED).
        """
        # MRO: _HerdScopedMixin.perform_create проверит org и сохранит instance,
        # но нам нужно дополнительно вызвать post_feed_consumption. Поэтому
        # дублируем валидацию org + сохраняем вручную.
        org = getattr(self.request, "organization", None)
        herd = serializer.validated_data.get("herd")
        if org and herd and herd.organization_id != org.id:
            raise DRFValidationError({"herd": "Стадо из другой организации."})
        instance = serializer.save(**self._save_kwargs_for_create(serializer))
        try:
            post_feed_consumption(instance, user=self.request.user)
        except FeedConsumptionPostError as exc:
            # DRF оборачивает request в atomic, поэтому исключение всё откатит.
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        from apps.audit.models import AuditLog
        self._write_audit(AuditLog.Action.CREATE, instance)
        from apps.audit.models import AuditLog
        self._write_audit(AuditLog.Action.CREATE, instance)
