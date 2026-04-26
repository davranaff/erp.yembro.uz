from decimal import Decimal
from datetime import date as date_type

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.lifecycle import DeleteReasonMixin, ImmutableStatusMixin
from apps.common.viewsets import OrgScopedModelViewSet

from .models import (
    DailyWeighing,
    FeedlotBatch,
    FeedlotFeedConsumption,
    FeedlotMortality,
)
from .serializers import (
    DailyWeighingSerializer,
    FeedlotBatchSerializer,
    FeedlotFeedConsumptionSerializer,
    FeedlotMortalitySerializer,
)
from .services.feed_consumption import (
    FeedConsumptionError,
    post_feed_consumption,
)
from .services.fcr import get_kpi
from .services.mortality import MortalityError, apply_mortality
from .services.place_batch import FeedlotPlaceError, place_feedlot_batch
from .services.ship import ShipToSlaughterError, ship_to_slaughter
from .services.weighing import WeighingError, record_weighing


class FeedlotBatchViewSet(ImmutableStatusMixin, OrgScopedModelViewSet):
    serializer_class = FeedlotBatchSerializer
    queryset = FeedlotBatch.objects.select_related(
        "house_block", "batch", "technologist"
    )
    module_code = "feedlot"
    immutable_statuses = ("shipped",)
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "house_block", "batch"]
    search_fields = ["doc_number"]
    ordering = ["-placed_date"]

    @action(detail=False, methods=["post"])
    def place(self, request):
        """POST /api/feedlot/batches/place/
        Создать FeedlotBatch для партии, пришедшей из инкубации.

        Body: {
            "batch": uuid,
            "house_block": uuid,
            "placed_date": "YYYY-MM-DD",
            "technologist": uuid,
            "initial_heads": int (optional — default batch.current_quantity),
            "target_weight_kg": decimal (optional),
            "target_slaughter_date": "YYYY-MM-DD" (optional),
            "doc_number": str (optional),
            "notes": str (optional)
        }
        """
        from apps.batches.models import Batch
        from apps.warehouses.models import ProductionBlock
        from apps.users.models import User

        try:
            batch = Batch.objects.get(pk=request.data["batch"])
            hb = ProductionBlock.objects.get(pk=request.data["house_block"])
            tech = User.objects.get(pk=request.data["technologist"])
            placed_date = date_type.fromisoformat(request.data["placed_date"])
        except (KeyError, Batch.DoesNotExist, ProductionBlock.DoesNotExist, User.DoesNotExist, ValueError) as exc:
            raise DRFValidationError({"__all__": f"Некорректные параметры: {exc}"})

        target_weight = request.data.get("target_weight_kg")
        target_slaughter = request.data.get("target_slaughter_date")
        try:
            result = place_feedlot_batch(
                batch,
                house_block=hb,
                placed_date=placed_date,
                technologist=tech,
                initial_heads=int(request.data["initial_heads"]) if request.data.get("initial_heads") is not None else None,
                target_weight_kg=Decimal(str(target_weight)) if target_weight is not None else None,
                target_slaughter_date=date_type.fromisoformat(target_slaughter) if target_slaughter else None,
                doc_number=request.data.get("doc_number"),
                notes=request.data.get("notes", ""),
                user=request.user,
            )
        except FeedlotPlaceError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        return Response(self.get_serializer(result.feedlot_batch).data, status=201)

    @action(detail=True, methods=["post"])
    def ship(self, request, pk=None):
        """POST /api/feedlot/batches/{id}/ship/

        Body: {
            "slaughter_line": uuid,
            "slaughter_warehouse": uuid,
            "source_warehouse": uuid,
            "quantity": "1000" (optional)
        }
        """
        from apps.warehouses.models import ProductionBlock, Warehouse

        feedlot_batch = self.get_object()

        try:
            line = ProductionBlock.objects.get(pk=request.data["slaughter_line"])
            sl_wh = Warehouse.objects.get(pk=request.data["slaughter_warehouse"])
            src_wh = Warehouse.objects.get(pk=request.data["source_warehouse"])
        except (KeyError, ProductionBlock.DoesNotExist, Warehouse.DoesNotExist) as exc:
            raise DRFValidationError(
                {"__all__": f"Неверные ссылки: {exc}"}
            )

        qty = request.data.get("quantity")
        qty_dec = Decimal(str(qty)) if qty is not None else None

        try:
            result = ship_to_slaughter(
                feedlot_batch,
                slaughter_line=line,
                slaughter_warehouse=sl_wh,
                source_warehouse=src_wh,
                quantity=qty_dec,
                user=request.user,
            )
        except ShipToSlaughterError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        feedlot_batch.refresh_from_db()
        data = self.get_serializer(feedlot_batch).data
        data["_result"] = {
            "transfer": {
                "id": str(result.transfer.id),
                "doc_number": result.transfer.doc_number,
                "state": result.transfer.state,
            }
        }
        return Response(data)

    @action(detail=True, methods=["post"])
    def mortality(self, request, pk=None):
        """POST /api/feedlot/batches/{id}/mortality/

        Body: {"date": "YYYY-MM-DD", "day_of_age": int, "dead_count": int,
               "cause": str, "notes": str}
        """
        feedlot_batch = self.get_object()
        try:
            date_val = date_type.fromisoformat(request.data["date"])
            day = int(request.data["day_of_age"])
            dead = int(request.data["dead_count"])
        except (KeyError, ValueError) as exc:
            raise DRFValidationError(
                {"__all__": f"Некорректные входные параметры: {exc}"}
            )

        try:
            result = apply_mortality(
                feedlot_batch,
                date=date_val,
                day_of_age=day,
                dead_count=dead,
                cause=request.data.get("cause", ""),
                notes=request.data.get("notes", ""),
                user=request.user,
            )
        except MortalityError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        feedlot_batch.refresh_from_db()
        data = self.get_serializer(feedlot_batch).data
        data["_result"] = {
            "record_id": str(result.record.id),
            "batch_current_quantity": str(result.batch.current_quantity),
            "loss_amount_uzs": str(result.loss_amount_uzs),
            "journal_entry_doc": (
                result.journal_entry.doc_number if result.journal_entry else None
            ),
        }
        return Response(data)

    @action(detail=True, methods=["post"], url_path="weighing")
    def weighing(self, request, pk=None):
        """POST /api/feedlot/batches/{id}/weighing/

        Body: {"date": "YYYY-MM-DD", "day_of_age": int, "sample_size": int,
               "avg_weight_kg": "X.XXX", "notes": str}

        Создаёт DailyWeighing + рассчитывает gain_kg от прошлого взвешивания
        + автоматические status transitions (PLACED→GROWING после первого
        взвешивания; GROWING→READY_SLAUGHTER если avg ≥ target).
        """
        feedlot_batch = self.get_object()
        try:
            date_val = date_type.fromisoformat(request.data["date"])
            day = int(request.data["day_of_age"])
            sample = int(request.data["sample_size"])
            avg = Decimal(str(request.data["avg_weight_kg"]))
        except (KeyError, ValueError) as exc:
            raise DRFValidationError(
                {"__all__": f"Некорректные параметры: {exc}"}
            )

        try:
            result = record_weighing(
                feedlot_batch,
                date=date_val,
                day_of_age=day,
                sample_size=sample,
                avg_weight_kg=avg,
                notes=request.data.get("notes", ""),
                user=request.user,
            )
        except WeighingError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        feedlot_batch.refresh_from_db()
        data = self.get_serializer(feedlot_batch).data
        data["_result"] = {
            "weighing_id": str(result.weighing.id),
            "gain_kg": str(result.weighing.gain_kg) if result.weighing.gain_kg else None,
            "status_changed": result.status_changed,
            "new_status": feedlot_batch.status if result.status_changed else None,
        }
        return Response(data)

    @action(detail=True, methods=["post"], url_path="feed_consumption")
    def feed_consumption(self, request, pk=None):
        """POST /api/feedlot/batches/{id}/feed_consumption/

        Body: {
            "feed_batch": uuid,
            "total_kg": "X.XXX",
            "period_from_day": int,
            "period_to_day": int,
            "feed_type": "start" | "growth" | "finish",
            "notes": str
        }

        Списывает корм со склада + создаёт JE Дт 20.02 / Кт 10.05 +
        накапливает cost на batch + рассчитывает per_head_g и period_fcr.
        """
        from apps.feed.models import FeedBatch

        feedlot_batch = self.get_object()
        try:
            feed_batch = FeedBatch.objects.get(pk=request.data["feed_batch"])
            total = Decimal(str(request.data["total_kg"]))
            from_day = int(request.data["period_from_day"])
            to_day = int(request.data["period_to_day"])
            feed_type = request.data["feed_type"]
        except (KeyError, ValueError, FeedBatch.DoesNotExist) as exc:
            raise DRFValidationError(
                {"__all__": f"Некорректные параметры: {exc}"}
            )

        try:
            result = post_feed_consumption(
                feedlot_batch,
                feed_batch=feed_batch,
                total_kg=total,
                period_from_day=from_day,
                period_to_day=to_day,
                feed_type=feed_type,
                notes=request.data.get("notes", ""),
                user=request.user,
            )
        except FeedConsumptionError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        feedlot_batch.refresh_from_db()
        data = self.get_serializer(feedlot_batch).data
        data["_result"] = {
            "consumption_id": str(result.consumption.id),
            "amount_uzs": str(result.amount_uzs),
            "journal_entry_doc": result.journal_entry.doc_number,
            "feed_batch_remaining_kg": str(result.feed_batch.current_quantity_kg),
            "period_fcr": (
                str(result.consumption.period_fcr)
                if result.consumption.period_fcr is not None else None
            ),
        }
        return Response(data)

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        """GET /api/feedlot/batches/{id}/stats/

        Сводный KPI: дни на откорме, поголовье, FCR, выживаемость и т.д.
        """
        from datetime import date as date_cls
        from datetime import timedelta

        feedlot_batch = self.get_object()
        kpi = get_kpi(feedlot_batch)

        # Прогноз даты убоя — линейная экстраполяция от текущего avg к target
        projected = None
        if (
            kpi.current_avg_weight_kg
            and feedlot_batch.target_weight_kg
            and kpi.days_on_feedlot > 0
            and kpi.current_avg_weight_kg < feedlot_batch.target_weight_kg
            and kpi.initial_avg_weight_kg is not None
        ):
            try:
                avg_daily_gain = (
                    (kpi.current_avg_weight_kg - kpi.initial_avg_weight_kg)
                    / Decimal(kpi.days_on_feedlot)
                )
                if avg_daily_gain > 0:
                    days_to_target = (
                        (feedlot_batch.target_weight_kg - kpi.current_avg_weight_kg)
                        / avg_daily_gain
                    )
                    projected = (
                        date_cls.today() + timedelta(days=int(days_to_target))
                    ).isoformat()
            except (ZeroDivisionError, ValueError):
                pass

        return Response({
            "batch_id": str(feedlot_batch.id),
            "days_on_feedlot": kpi.days_on_feedlot,
            "initial_heads": kpi.initial_heads,
            "current_heads": kpi.current_heads,
            "dead_count": kpi.dead_count,
            "survival_pct": str(kpi.survival_pct),
            "total_mortality_pct": str(kpi.total_mortality_pct),
            "current_avg_weight_kg": (
                str(kpi.current_avg_weight_kg)
                if kpi.current_avg_weight_kg is not None else None
            ),
            "initial_avg_weight_kg": (
                str(kpi.initial_avg_weight_kg)
                if kpi.initial_avg_weight_kg is not None else None
            ),
            "total_gain_kg": str(kpi.total_gain_kg),
            "total_feed_kg": str(kpi.total_feed_kg),
            "total_fcr": str(kpi.total_fcr) if kpi.total_fcr is not None else None,
            "target_weight_kg": str(feedlot_batch.target_weight_kg),
            "target_slaughter_date": (
                feedlot_batch.target_slaughter_date.isoformat()
                if feedlot_batch.target_slaughter_date else None
            ),
            "projected_slaughter_date": projected,
            "status": feedlot_batch.status,
        })

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        """GET /api/feedlot/batches/{id}/timeline/

        Единый таймлайн: placed, weighing, feed, mortality, shipped.
        """
        feedlot_batch = self.get_object()
        events: list[dict] = []

        # 1. Placement
        events.append({
            "type": "placed",
            "date": feedlot_batch.placed_date.isoformat(),
            "id": f"placed-{feedlot_batch.id}",
            "title": f"Посадка партии {feedlot_batch.doc_number}",
            "subtitle": (
                f"{feedlot_batch.initial_heads} гол · "
                f"шкаф {feedlot_batch.house_block.code if feedlot_batch.house_block_id else '—'} · "
                f"цель {feedlot_batch.target_weight_kg} кг"
            ),
            "notes": "",
        })

        # 2. Weighings
        for w in DailyWeighing.objects.filter(feedlot_batch=feedlot_batch):
            events.append({
                "type": "weighing",
                "date": w.date.isoformat(),
                "id": str(w.id),
                "title": f"Взвешивание · день {w.day_of_age}",
                "subtitle": (
                    f"проба {w.sample_size} гол · ср. вес {w.avg_weight_kg} кг"
                    + (f" · привес +{w.gain_kg} кг" if w.gain_kg else "")
                ),
                "notes": w.notes or "",
            })

        # 3. Feed consumption
        for fc in FeedlotFeedConsumption.objects.filter(
            feedlot_batch=feedlot_batch,
        ).select_related("feed_batch"):
            # Дата = условно period_from_day → placed_date + period_from_day
            from datetime import timedelta
            ev_date = (
                feedlot_batch.placed_date + timedelta(days=fc.period_from_day)
            ).isoformat() if feedlot_batch.placed_date else fc.created_at.date().isoformat()
            events.append({
                "type": "feed",
                "date": ev_date,
                "id": str(fc.id),
                "title": f"Кормление · {fc.get_feed_type_display()}",
                "subtitle": (
                    f"{fc.total_kg} кг · дни {fc.period_from_day}–{fc.period_to_day}"
                    + (f" · из партии {fc.feed_batch.doc_number}" if fc.feed_batch_id else "")
                    + (f" · FCR {fc.period_fcr}" if fc.period_fcr is not None else "")
                ),
                "notes": fc.notes or "",
            })

        # 4. Mortality
        for m in FeedlotMortality.objects.filter(feedlot_batch=feedlot_batch):
            events.append({
                "type": "mortality",
                "date": m.date.isoformat(),
                "id": str(m.id),
                "title": f"Падёж · {m.dead_count} гол",
                "subtitle": (
                    f"день {m.day_of_age}"
                    + (f" · причина: {m.cause}" if m.cause else "")
                ),
                "notes": m.notes or "",
            })

        # 5. Shipped
        if feedlot_batch.status == FeedlotBatch.Status.SHIPPED:
            events.append({
                "type": "shipped",
                "date": feedlot_batch.updated_at.date().isoformat(),
                "id": f"shipped-{feedlot_batch.id}",
                "title": "Передано на убой",
                "subtitle": (
                    f"осталось {feedlot_batch.current_heads} гол"
                ),
                "notes": "",
            })

        TYPE_PRIORITY = {
            "shipped": 0, "mortality": 1, "weighing": 2, "feed": 3, "placed": 4,
        }
        events.sort(
            key=lambda e: (e["date"], -TYPE_PRIORITY.get(e["type"], 99)),
            reverse=True,
        )

        counts: dict[str, int] = {}
        for e in events:
            counts[e["type"]] = counts.get(e["type"], 0) + 1

        return Response({
            "batch_id": str(feedlot_batch.id),
            "events": events,
            "counts": counts,
        })


class _ChildOfBatchMixin:
    """
    Для дочерних feedlot-моделей (DailyWeighing, FeedlotFeedConsumption,
    FeedlotMortality): organization_field = "feedlot_batch__organization",
    но самой organization-колонки нет. Возвращаем {} из save_kwargs.
    """

    def _save_kwargs_for_create(self, serializer) -> dict:
        return {}


class DailyWeighingViewSet(DeleteReasonMixin, _ChildOfBatchMixin, OrgScopedModelViewSet):
    serializer_class = DailyWeighingSerializer
    queryset = DailyWeighing.objects.select_related("feedlot_batch")
    module_code = "feedlot"
    organization_field = "feedlot_batch__organization"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["feedlot_batch", "day_of_age"]
    ordering = ["-date"]


class FeedlotFeedConsumptionViewSet(DeleteReasonMixin, _ChildOfBatchMixin, OrgScopedModelViewSet):
    serializer_class = FeedlotFeedConsumptionSerializer
    queryset = FeedlotFeedConsumption.objects.select_related(
        "feedlot_batch", "feed_batch"
    )
    module_code = "feedlot"
    organization_field = "feedlot_batch__organization"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["feedlot_batch", "feed_type"]


class FeedlotMortalityViewSet(DeleteReasonMixin, _ChildOfBatchMixin, OrgScopedModelViewSet):
    serializer_class = FeedlotMortalitySerializer
    queryset = FeedlotMortality.objects.select_related("feedlot_batch")
    module_code = "feedlot"
    organization_field = "feedlot_batch__organization"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["feedlot_batch"]
    ordering = ["-date"]
