from datetime import date as date_type, timedelta
from decimal import Decimal

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.lifecycle import DeleteReasonMixin, ImmutableStatusMixin
from apps.common.viewsets import OrgScopedModelViewSet

from .models import IncubationRegimeDay, IncubationRun, MirageInspection
from .serializers import (
    IncubationRegimeDaySerializer,
    IncubationRunSerializer,
    MirageInspectionSerializer,
)
from .services.cancel import (
    IncubationCancelError,
    cancel_incubation_run,
)
from .services.hatch import IncubationHatchError, hatch_incubation_run
from .services.load_eggs import LoadEggsError, load_eggs_to_incubator
from .services.transfer_to_hatcher import (
    IncubationTransferError,
    transfer_to_hatcher,
)


class IncubationRunViewSet(ImmutableStatusMixin, OrgScopedModelViewSet):
    serializer_class = IncubationRunSerializer
    queryset = IncubationRun.objects.select_related(
        "incubator_block", "hatcher_block", "batch", "technologist",
        "batch__current_module", "batch__nomenclature",
    )
    module_code = "incubation"
    immutable_statuses = ("transferred", "cancelled")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "incubator_block", "hatcher_block", "batch"]
    search_fields = ["doc_number"]
    ordering_fields = ["loaded_date", "doc_number"]
    ordering = ["-loaded_date"]

    def perform_create(self, serializer):
        """
        Создание IncubationRun идёт через сервис load_eggs_to_incubator
        с полноценными guards (origin matochnik, current module incubation,
        block kind, batch quantity).
        """
        vd = serializer.validated_data
        org = getattr(self.request, "organization", None)
        try:
            result = load_eggs_to_incubator(
                organization=org,
                module=vd["module"],
                batch=vd["batch"],
                incubator_block=vd["incubator_block"],
                loaded_date=vd["loaded_date"],
                eggs_loaded=vd["eggs_loaded"],
                technologist=vd["technologist"],
                days_total=vd.get("days_total", 21),
                expected_hatch_date=vd.get("expected_hatch_date"),
                doc_number=vd.get("doc_number", "") or "",
                notes=vd.get("notes", ""),
                user=self.request.user,
            )
        except LoadEggsError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        # Подменяем instance в сериализаторе чтобы DRF вернул полный объект.
        serializer.instance = result.run
        from apps.audit.models import AuditLog
        self._write_audit(AuditLog.Action.CREATE, result.run)

    @action(detail=True, methods=["post"])
    def hatch(self, request, pk=None):
        """POST /api/incubation/runs/{id}/hatch/

        Body: {
          "chick_nomenclature": uuid, "hatched_count": int,
          "discarded_count": int (opt), "actual_hatch_date": "YYYY-MM-DD" (opt)
        }
        """
        from apps.nomenclature.models import NomenclatureItem

        run = self.get_object()
        nom_id = request.data.get("chick_nomenclature")
        if not nom_id:
            raise DRFValidationError({"chick_nomenclature": "Обязательно."})
        try:
            nom = NomenclatureItem.objects.get(pk=nom_id)
        except NomenclatureItem.DoesNotExist:
            raise DRFValidationError({"chick_nomenclature": "Не найдена."})

        hatched = request.data.get("hatched_count")
        discarded = request.data.get("discarded_count")
        actual = request.data.get("actual_hatch_date")

        actual_date = date_type.fromisoformat(actual) if actual else None

        try:
            result = hatch_incubation_run(
                run,
                chick_nomenclature=nom,
                hatched_count=int(hatched) if hatched is not None else None,
                discarded_count=int(discarded) if discarded is not None else None,
                actual_hatch_date=actual_date,
                user=request.user,
            )
        except IncubationHatchError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        run.refresh_from_db()
        data = self.get_serializer(run).data
        data["_result"] = {
            "chick_batch": {
                "id": str(result.chick_batch.id),
                "doc_number": result.chick_batch.doc_number,
                "quantity": str(result.chick_batch.current_quantity),
            },
            "egg_batch_state": result.egg_batch.state,
            "writeoff_amount_uzs": str(result.writeoff_amount_uzs),
            "writeoff_je_doc": (
                result.writeoff_je.doc_number if result.writeoff_je else None
            ),
        }
        return Response(data)

    @action(detail=True, methods=["post"], url_path="transfer-to-hatcher")
    def transfer_to_hatcher_action(self, request, pk=None):
        """POST /api/incubation/runs/{id}/transfer-to-hatcher/
        Body: {"hatcher_block": uuid}
        """
        from apps.warehouses.models import ProductionBlock

        run = self.get_object()
        hb_id = request.data.get("hatcher_block")
        if not hb_id:
            raise DRFValidationError({"hatcher_block": "Обязательно."})
        try:
            hb = ProductionBlock.objects.get(pk=hb_id)
        except ProductionBlock.DoesNotExist:
            raise DRFValidationError({"hatcher_block": "Не найден."})
        try:
            transfer_to_hatcher(run, hatcher_block=hb, user=request.user)
        except IncubationTransferError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        run.refresh_from_db()
        return Response(self.get_serializer(run).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """POST /api/incubation/runs/{id}/cancel/
        Body: {"reason": str (opt)}
        """
        run = self.get_object()
        reason = request.data.get("reason", "")
        try:
            result = cancel_incubation_run(run, reason=reason, user=request.user)
        except IncubationCancelError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        run.refresh_from_db()
        data = self.get_serializer(run).data
        data["_result"] = {
            "writeoff_amount_uzs": str(result.writeoff_amount_uzs),
            "writeoff_je_doc": (
                result.writeoff_je.doc_number if result.writeoff_je else None
            ),
        }
        return Response(data)

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        """
        GET /api/incubation/runs/{id}/stats/

        Сводка по run:
            current_day, days_remaining, hatchability_pct, mortality_pct,
            eggs_remaining (current из batch), regime_days_count,
            mirage_inspections_count, last_temp/humidity (последний замер).
        """
        run = self.get_object()
        ser = self.get_serializer(run).data

        # Последний замер режима (для UI — «сейчас в шкафу N°C, H%»)
        last_regime = (
            IncubationRegimeDay.objects.filter(run=run)
            .order_by("-day").first()
        )
        # Счётчики
        regime_count = IncubationRegimeDay.objects.filter(run=run).count()
        mirage_count = MirageInspection.objects.filter(run=run).count()

        eggs_remaining = int(run.batch.current_quantity) if run.batch_id else 0

        return Response({
            "run_id": str(run.id),
            "status": run.status,
            "current_day": ser["current_day"],
            "days_remaining": ser["days_remaining"],
            "hatchability_pct": ser["hatchability_pct"],
            "mortality_pct": ser["mortality_pct"],
            "eggs_loaded": run.eggs_loaded,
            "eggs_remaining": eggs_remaining,
            "hatched_count": run.hatched_count,
            "discarded_count": run.discarded_count,
            "regime_days_count": regime_count,
            "mirage_inspections_count": mirage_count,
            "last_regime_temp_c": (
                str(last_regime.actual_temperature_c or last_regime.temperature_c)
                if last_regime else None
            ),
            "last_regime_humidity_pct": (
                str(last_regime.actual_humidity_percent or last_regime.humidity_percent)
                if last_regime else None
            ),
        })

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        """
        GET /api/incubation/runs/{id}/timeline/

        Единый таймлайн событий партии инкубации:
            load, regime, mirage, transfer_to_hatcher, hatch, cancel.
        Сортируется по дате (убывание).
        """
        run = self.get_object()
        events: list[dict] = []

        # 1. Загрузка (всегда первая)
        events.append({
            "type": "load",
            "date": run.loaded_date.isoformat(),
            "id": str(run.id),
            "title": f"Закладка партии {run.doc_number}",
            "subtitle": (
                f"{run.eggs_loaded} яиц · шкаф {run.incubator_block.code} · "
                f"партия-источник {run.batch.doc_number}"
            ),
            "notes": "",
        })

        # 2. Мираж
        for m in MirageInspection.objects.filter(run=run).select_related("inspector"):
            infertile = m.inspected_count - m.fertile_count
            events.append({
                "type": "mirage",
                "date": m.inspection_date.isoformat(),
                "id": str(m.id),
                "title": f"Овоскопия (день {m.day_of_incubation})",
                "subtitle": (
                    f"осмотрено {m.inspected_count}, оплод. {m.fertile_count}, "
                    f"брак {m.discarded_count}, неоплод ~{infertile}"
                ),
                "notes": m.notes or "",
                "inspector_name": (
                    m.inspector.full_name if m.inspector_id else None
                ),
            })

        # 3. Замеры режима
        for r in IncubationRegimeDay.objects.filter(run=run).select_related("observed_by"):
            # Используем observed_at если есть, иначе loaded_date + day
            d = (
                r.observed_at.date() if r.observed_at
                else (run.loaded_date + timedelta(days=r.day - 1))
            )
            events.append({
                "type": "regime",
                "date": d.isoformat(),
                "id": str(r.id),
                "title": f"Режим · день {r.day}",
                "subtitle": (
                    f"T {r.actual_temperature_c or r.temperature_c}°C · "
                    f"H {r.actual_humidity_percent or r.humidity_percent}% · "
                    f"{r.egg_turns_per_day} поворотов"
                ),
                "notes": r.notes or "",
            })

        # 4. Передача на выводной (если hatcher_block задан — считаем что была)
        if run.hatcher_block_id and run.status in (
            IncubationRun.Status.HATCHING,
            IncubationRun.Status.TRANSFERRED,
        ):
            # Дата неизвестна точно, ставим expected_hatch − 3 дня как heuristic
            xfer_date = (run.expected_hatch_date - timedelta(days=3)).isoformat()
            events.append({
                "type": "transfer_to_hatcher",
                "date": xfer_date,
                "id": f"xfer-{run.id}",
                "title": f"Перевод на выводной шкаф {run.hatcher_block.code}",
                "subtitle": "подготовка к наклёву",
                "notes": "",
            })

        # 5. Вывод / отмена
        if run.status == IncubationRun.Status.TRANSFERRED and run.actual_hatch_date:
            events.append({
                "type": "hatch",
                "date": run.actual_hatch_date.isoformat(),
                "id": f"hatch-{run.id}",
                "title": "Вывод молодняка",
                "subtitle": (
                    f"выведено {run.hatched_count or 0}, отбраковано "
                    f"{run.discarded_count or 0}"
                ),
                "notes": "",
            })
        if run.status == IncubationRun.Status.CANCELLED:
            events.append({
                "type": "cancel",
                "date": (run.actual_hatch_date or run.loaded_date).isoformat(),
                "id": f"cancel-{run.id}",
                "title": "Отмена партии",
                "subtitle": "",
                "notes": run.notes or "",
            })

        TYPE_PRIORITY = {
            "cancel": 0, "hatch": 1, "transfer_to_hatcher": 2,
            "mirage": 3, "regime": 4, "load": 5,
        }
        events.sort(
            key=lambda ev: (ev["date"], -TYPE_PRIORITY.get(ev["type"], 99)),
            reverse=True,
        )

        counts: dict[str, int] = {}
        for ev in events:
            counts[ev["type"]] = counts.get(ev["type"], 0) + 1

        return Response({
            "run_id": str(run.id),
            "events": events,
            "counts": counts,
        })


class _RunScopedMixin:
    """
    Для child-моделей (IncubationRegimeDay, MirageInspection): поле `run`
    ведёт к organization через run.organization. OrgScopedModelViewSet по
    умолчанию кладёт `run__organization=<org>` в serializer.save() —
    это невалидный kwarg. Возвращаем {} и вручную валидируем org.
    """

    def _save_kwargs_for_create(self, serializer) -> dict:
        kwargs: dict = {}
        model = serializer.Meta.model if hasattr(serializer, "Meta") else None
        if model is not None:
            field_names = {f.name for f in model._meta.get_fields()}
            user = getattr(self.request, "user", None)
            if user and getattr(user, "is_authenticated", False):
                for auto_field in ("observed_by", "inspector", "created_by"):
                    # Автоматически подставляем текущего пользователя если поле есть
                    # и не задано во входных данных.
                    if auto_field in field_names and auto_field not in serializer.validated_data:
                        kwargs[auto_field] = user
        return kwargs

    def perform_create(self, serializer):  # type: ignore[override]
        org = getattr(self.request, "organization", None)
        run = serializer.validated_data.get("run")
        if org and run and run.organization_id != org.id:
            raise DRFValidationError({"run": "Партия из другой организации."})
        instance = serializer.save(**self._save_kwargs_for_create(serializer))
        from apps.audit.models import AuditLog
        self._write_audit(AuditLog.Action.CREATE, instance)
        return instance


class IncubationRegimeDayViewSet(DeleteReasonMixin, _RunScopedMixin, OrgScopedModelViewSet):
    serializer_class = IncubationRegimeDaySerializer
    queryset = IncubationRegimeDay.objects.select_related("run", "observed_by")
    module_code = "incubation"
    organization_field = "run__organization"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["run", "day"]
    ordering = ["run", "day"]


class MirageInspectionViewSet(DeleteReasonMixin, _RunScopedMixin, OrgScopedModelViewSet):
    serializer_class = MirageInspectionSerializer
    queryset = MirageInspection.objects.select_related("run", "inspector")
    module_code = "incubation"
    organization_field = "run__organization"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["run"]
    ordering = ["-inspection_date"]
