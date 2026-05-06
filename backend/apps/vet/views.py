import secrets

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status as drf_status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.common.viewsets import OrgScopedModelViewSet

from .models import (
    SellerDeviceToken,
    VaccinationSchedule,
    VaccinationScheduleItem,
    VetAccessory,
    VetDrug,
    VetStockBatch,
    VetTreatmentLog,
)
from .serializers import (
    SellerDeviceTokenCreateSerializer,
    SellerDeviceTokenSerializer,
    VaccinationScheduleItemSerializer,
    VaccinationScheduleSerializer,
    VetAccessorySerializer,
    VetDrugSerializer,
    VetStockBatchSerializer,
    VetTreatmentLogSerializer,
)
from .services.apply_treatment import (
    VetTreatmentApplyError,
    apply_vet_treatment,
)
from .services.cancel import VetTreatmentCancelError, cancel_vet_treatment
from .services.receive_accessory import (
    VetAccessoryReceiveError,
    receive_vet_accessory,
)
from .services.receive_stock import (
    VetStockReceiveError,
    receive_vet_stock_batch,
    release_vet_stock_from_quarantine,
)
from .services.recall import VetRecallError, recall_vet_stock_batch


class VetDrugViewSet(OrgScopedModelViewSet):
    serializer_class = VetDrugSerializer
    queryset = VetDrug.objects.select_related("nomenclature")
    module_code = "vet"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["drug_type", "administration_route", "is_active"]
    search_fields = ["nomenclature__sku", "nomenclature__name", "barcode"]
    ordering = ["nomenclature__sku"]

    def perform_create(self, serializer):
        from apps.audit.models import AuditLog
        kwargs = self._save_kwargs_for_create(serializer)
        # Auto-barcode для shelf-tag (этикетка на полке).
        # Не путать с barcode у VetStockBatch — там штрих-код конкретного лота.
        if not serializer.validated_data.get("barcode"):
            sku = serializer.validated_data["nomenclature"].sku.upper()[:16]
            kwargs["barcode"] = f"VET-D-{sku}-{secrets.token_hex(2).upper()}"
        instance = serializer.save(**kwargs)
        self._write_audit(AuditLog.Action.CREATE, instance)


class VetStockBatchViewSet(OrgScopedModelViewSet):
    serializer_class = VetStockBatchSerializer
    queryset = VetStockBatch.objects.select_related(
        "drug__nomenclature", "warehouse", "supplier", "unit"
    )
    module_code = "vet"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["drug", "warehouse", "status"]
    search_fields = [
        "doc_number",
        "lot_number",
        "barcode",
        "drug__nomenclature__sku",
        "drug__nomenclature__name",
    ]
    ordering = ["-received_date"]

    @action(detail=False, methods=["post"])
    def receive(self, request):
        """POST /api/vet/stock-batches/receive/
        Приёмка партии препарата на карантин.
        Body: {
            "drug": uuid, "lot_number": str, "warehouse": uuid, "supplier": uuid,
            "purchase": uuid (REQUIRED),
            "received_date": "YYYY-MM-DD", "expiration_date": "YYYY-MM-DD",
            "quantity": decimal, "unit": uuid, "price_per_unit_uzs": decimal,
            "quarantine_until": "YYYY-MM-DD" (optional),
            "barcode": str (optional, авто-генерится),
            "notes": str (optional)
        }
        """
        from datetime import date as date_type
        from decimal import Decimal
        from apps.counterparties.models import Counterparty
        from apps.nomenclature.models import Unit
        from apps.purchases.models import PurchaseOrder
        from apps.warehouses.models import Warehouse

        try:
            drug = VetDrug.objects.get(pk=request.data["drug"])
            wh = Warehouse.objects.get(pk=request.data["warehouse"])
            supplier = Counterparty.objects.get(pk=request.data["supplier"])
            unit = Unit.objects.get(pk=request.data["unit"])
            received = date_type.fromisoformat(request.data["received_date"])
            expires = date_type.fromisoformat(request.data["expiration_date"])
            qty = Decimal(str(request.data["quantity"]))
            price = Decimal(str(request.data["price_per_unit_uzs"]))
        except (KeyError, VetDrug.DoesNotExist, Warehouse.DoesNotExist,
                Counterparty.DoesNotExist, Unit.DoesNotExist, ValueError) as exc:
            raise DRFValidationError({"__all__": f"Некорректные параметры: {exc}"})

        if not request.data.get("purchase"):
            raise DRFValidationError({
                "purchase": "Закуп обязателен (compliance). Создайте PurchaseOrder сначала."
            })
        try:
            purchase = PurchaseOrder.objects.get(pk=request.data["purchase"])
        except PurchaseOrder.DoesNotExist:
            raise DRFValidationError({"purchase": "Не найден."})

        q_until = request.data.get("quarantine_until")
        q_until_date = date_type.fromisoformat(q_until) if q_until else None

        try:
            result = receive_vet_stock_batch(
                organization=request.organization,
                drug=drug,
                lot_number=request.data["lot_number"],
                warehouse=wh,
                supplier=supplier,
                received_date=received,
                expiration_date=expires,
                quantity=qty,
                unit=unit,
                price_per_unit_uzs=price,
                purchase=purchase,
                quarantine_until=q_until_date,
                barcode=request.data.get("barcode") or None,
                notes=request.data.get("notes", ""),
                user=request.user,
            )
        except VetStockReceiveError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        return Response(self.get_serializer(result.stock_batch).data, status=201)

    @action(detail=True, methods=["post"], url_path="release-quarantine")
    def release_quarantine(self, request, pk=None):
        """POST /api/vet/stock-batches/{id}/release-quarantine/"""
        sb = self.get_object()
        try:
            release_vet_stock_from_quarantine(sb, user=request.user)
        except VetStockReceiveError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        sb.refresh_from_db()
        return Response(self.get_serializer(sb).data)

    @action(detail=True, methods=["post"])
    def recall(self, request, pk=None):
        """POST /api/vet/stock-batches/{id}/recall/

        Body: {"reason": str (мин. 3 симв.)}

        Отзывает лот с реверсом всех связанных лечений.
        """
        sb = self.get_object()
        reason = request.data.get("reason", "")
        try:
            result = recall_vet_stock_batch(sb, reason=reason, user=request.user)
        except VetRecallError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        sb.refresh_from_db()
        data = self.get_serializer(sb).data
        data["_result"] = {
            "cancelled_treatments_count": len(result.cancelled_treatments),
        }
        return Response(data)

    @action(detail=False, methods=["get"], url_path="by-barcode")
    def by_barcode(self, request):
        """GET /api/vet/stock-batches/by-barcode/?barcode=X"""
        barcode = request.query_params.get("barcode")
        if not barcode:
            raise DRFValidationError({"barcode": "Обязательно."})
        qs = self.get_queryset().filter(barcode=barcode)
        sb = qs.first()
        if not sb:
            return Response(
                {"detail": "Лот не найден."},
                status=drf_status.HTTP_404_NOT_FOUND,
            )
        return Response(self.get_serializer(sb).data)


class VaccinationScheduleViewSet(OrgScopedModelViewSet):
    serializer_class = VaccinationScheduleSerializer
    queryset = VaccinationSchedule.objects.prefetch_related("items")
    module_code = "vet"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["direction", "is_active"]
    search_fields = ["code", "name"]
    ordering = ["code"]


class VaccinationScheduleItemViewSet(OrgScopedModelViewSet):
    serializer_class = VaccinationScheduleItemSerializer
    queryset = VaccinationScheduleItem.objects.select_related("drug__nomenclature")
    module_code = "vet"
    organization_field = "schedule__organization"
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["schedule", "drug", "is_mandatory"]


class VetTreatmentLogViewSet(OrgScopedModelViewSet):
    """
    /api/vet/treatments/ — журнал применения препаратов.
    POST /api/vet/treatments/{id}/apply/ — провести (сервис).
    POST /api/vet/treatments/{id}/cancel/ — отменить (с reverse JE).
    POST /api/vet/treatments/{id}/acknowledge/ — менеджер модуля-цели подтвердил.
    GET  /api/vet/treatments/incoming/?to_module=<code> — inbox для модуля-цели.
    GET  /api/vet/treatments/timeline/?batch=<uuid>|herd=<uuid> — хронология.
    """

    serializer_class = VetTreatmentLogSerializer
    queryset = VetTreatmentLog.objects.select_related(
        "drug__nomenclature", "stock_batch", "target_block",
        "target_block__module",
        "target_batch", "target_batch__current_module",
        "target_herd", "target_herd__module",
        "unit", "veterinarian",
    )
    module_code = "vet"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "drug",
        "target_batch",
        "target_herd",
        "target_block",
        "indication",
        "stock_batch",
    ]
    search_fields = ["doc_number", "notes"]
    ordering = ["-treatment_date"]

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        """Провести лечение (декремент лота + withdrawal + JE).

        После проведения уведомляет менеджеров модуля-цели через TG
        (`apps.tgbot.notify_admins_task`) — soft-acknowledgement: они
        увидят нотификацию + запись в inbox `/incoming/?to_module=...`.
        Применение не блокируется acknowledgement-ом.
        """
        treatment = self.get_object()
        try:
            result = apply_vet_treatment(treatment, user=request.user)
        except VetTreatmentApplyError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        treatment.refresh_from_db()
        self._notify_target_module(treatment, result)
        data = self.get_serializer(treatment).data
        data["_result"] = {
            "stock_movement": {
                "id": str(result.stock_movement.id),
                "doc_number": result.stock_movement.doc_number,
                "amount_uzs": str(result.stock_movement.amount_uzs),
            },
            "journal_entry": {
                "id": str(result.journal_entry.id),
                "doc_number": result.journal_entry.doc_number,
            },
            "batch_cost_entry_id": (
                str(result.batch_cost_entry.id)
                if result.batch_cost_entry
                else None
            ),
            "withdrawal_period_ends": {
                "previous": (
                    result.previous_withdrawal_end.isoformat()
                    if result.previous_withdrawal_end
                    else None
                ),
                "new": (
                    result.new_withdrawal_end.isoformat()
                    if result.new_withdrawal_end
                    else None
                ),
            },
        }
        return Response(data)

    # Окно, в течение которого менеджер модуля-цели может отклонить
    # применение препарата (после этого — только vet/admin). 24ч даёт
    # owner'у партии шанс заметить ошибку до того как птица «уехала»
    # дальше по цепочке (продажа/убой), где реверс ломает учёт.
    REJECT_WINDOW_HOURS = 24

    def get_permissions(self):
        # `incoming` + `cancel` + `acknowledge` — особый RBAC: разрешаем
        # менеджерам модуля-цели (не только vet) с дополнительной валидацией
        # внутри action-а. См. `_can_user_cancel`.
        if getattr(self, "action", None) in ("incoming", "cancel", "acknowledge"):
            from rest_framework.permissions import IsAuthenticated
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """POST /api/vet/treatments/{id}/cancel/  body={reason}

        RBAC: разрешено если у пользователя есть rw-доступ к одному из:
          - vet (обычный кейс — ветеринар сам откатывает свою ошибку,
            доступно всегда)
          - target_module (feedlot/matochnik/...) — owner партии видит
            ошибку и хочет отклонить применение к своим птицам.
            Окно: только в первые `REJECT_WINDOW_HOURS` часов после
            apply (после этого птица уже могла быть продана/убита,
            реверс ломает учёт ниже по цепочке).

        Без rw ни к одному — 403.
        """
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.exceptions import PermissionDenied

        treatment = self.get_object()
        reason = request.data.get("reason", "")

        # RBAC поверх стандартного OrgScopedModelViewSet
        membership = getattr(request, "membership", None)
        if membership is None:
            raise PermissionDenied({"detail": "Нет членства в организации."})

        target_module = self._resolve_target_module(treatment)
        gate = self._can_user_cancel(membership, treatment, target_module)
        if not gate["allowed"]:
            raise PermissionDenied({"detail": gate["reason"]})

        try:
            result = cancel_vet_treatment(treatment, reason=reason, user=request.user)
        except VetTreatmentCancelError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        treatment.refresh_from_db()
        data = self.get_serializer(treatment).data
        data["_result"] = {
            "reversal_je_doc": result.reversal_je.doc_number,
            "reversal_sm_doc": (
                result.reversal_sm.doc_number if result.reversal_sm else None
            ),
            "new_withdrawal_end": (
                result.new_withdrawal_end.isoformat()
                if result.new_withdrawal_end
                else None
            ),
        }
        return Response(data)

    def _can_user_cancel(self, membership, treatment, target_module):
        """Проверяем кому разрешено отменять treatment.

        Возвращает {"allowed": bool, "reason": str}.

        Логика:
          - vet rw → можно всегда (ветеринар откатывает свою ошибку)
          - target_module rw → можно только в окно REJECT_WINDOW_HOURS
            после created_at (apply timestamp)
        """
        from datetime import timedelta
        from django.utils import timezone

        from apps.common.permissions import _effective_level, level_satisfies

        # 1. Vet rw → carte blanche
        if level_satisfies(_effective_level(membership, "vet"), "rw"):
            return {"allowed": True, "reason": ""}

        # 2. Target module rw → только в окно
        if target_module is not None and level_satisfies(
            _effective_level(membership, target_module.code), "rw"
        ):
            window_end = treatment.created_at + timedelta(
                hours=self.REJECT_WINDOW_HOURS
            )
            if timezone.now() <= window_end:
                return {"allowed": True, "reason": ""}
            return {
                "allowed": False,
                "reason": (
                    f"Окно отклонения истекло "
                    f"({self.REJECT_WINDOW_HOURS}ч после применения). "
                    f"Обратитесь к ветеринару для отмены."
                ),
            }

        return {
            "allowed": False,
            "reason": (
                "Нет прав на отмену: требуется rw к модулю vet "
                "или к модулю-цели применения."
            ),
        }

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        """POST /api/vet/treatments/{id}/acknowledge/

        Менеджер модуля-цели подтверждает, что видел запись о применении
        препарата. Soft-only — не отменяет, не реверсит проводки. Просто
        снимает уведомление в inbox.

        RBAC: пользователь должен иметь r+ доступ к target_module
        (feedlot/matochnik/incubation). Без этого — 403.
        """
        from django.utils import timezone
        from rest_framework.exceptions import PermissionDenied

        from apps.audit.models import AuditLog
        from apps.audit.services.writer import audit_log
        from apps.common.permissions import _effective_level, level_satisfies

        treatment = self.get_object()
        if treatment.acknowledged_at is not None:
            return Response(self.get_serializer(treatment).data)

        target_module = self._resolve_target_module(treatment)
        if target_module is None:
            raise DRFValidationError(
                {"__all__": "Не удалось определить модуль-цель для подтверждения."}
            )

        membership = getattr(request, "membership", None)
        if membership is None or not level_satisfies(
            _effective_level(membership, target_module.code), "r"
        ):
            raise PermissionDenied(
                {"detail": f"Нет доступа к модулю '{target_module.code}'."}
            )

        treatment.acknowledged_at = timezone.now()
        treatment.acknowledged_by = request.user
        treatment.save(
            update_fields=["acknowledged_at", "acknowledged_by", "updated_at"]
        )
        audit_log(
            organization=treatment.organization,
            module=target_module,
            actor=request.user,
            action=AuditLog.Action.UPDATE,
            entity=treatment,
            action_verb=f"acknowledged vet treatment {treatment.doc_number}",
        )
        return Response(self.get_serializer(treatment).data)

    @action(detail=False, methods=["get"], url_path="incoming")
    def incoming(self, request):
        """GET /api/vet/treatments/incoming/?to_module=<code>

        Inbox менеджера модуля-цели: применённые (есть proведённый JE)
        и ещё не подтверждённые (`acknowledged_at IS NULL`) treatment'ы,
        чей target лежит в указанном модуле.

        RBAC:
          - user должен иметь r+ к запрошенному `to_module`
          - без `to_module` — отдаём по всем модулям где есть r+
        """
        from django.contrib.contenttypes.models import ContentType

        from apps.accounting.models import JournalEntry
        from apps.common.permissions import _effective_level, level_satisfies
        from apps.modules.models import Module
        from rest_framework.exceptions import PermissionDenied

        org = getattr(request, "organization", None)
        membership = getattr(request, "membership", None)
        if org is None or membership is None:
            return Response([])

        to_module_code = request.query_params.get("to_module", "").strip()

        # Только проведённые (есть JournalEntry) и не отменённые лечения
        ct = ContentType.objects.get_for_model(VetTreatmentLog)
        applied_ids = JournalEntry.objects.filter(
            organization=org,
            source_content_type=ct,
        ).values_list("source_object_id", flat=True)

        qs = (
            self.get_queryset()
            .filter(
                organization=org,
                id__in=list(applied_ids),
                acknowledged_at__isnull=True,
                cancelled_at__isnull=True,
            )
        )

        # Фильтр по target_module — определяем по нескольким источникам:
        # target_block.module / target_batch.current_module / target_herd.module
        if to_module_code:
            if not level_satisfies(
                _effective_level(membership, to_module_code), "r"
            ):
                raise PermissionDenied(
                    {"detail": f"Нет доступа к модулю '{to_module_code}'."}
                )
            from django.db.models import Q
            qs = qs.filter(
                Q(target_block__module__code=to_module_code)
                | Q(target_batch__current_module__code=to_module_code)
                | Q(target_herd__module__code=to_module_code)
            )
        else:
            allowed_codes = [
                code
                for code in Module.objects.values_list("code", flat=True)
                if level_satisfies(_effective_level(membership, code), "r")
            ]
            from django.db.models import Q
            qs = qs.filter(
                Q(target_block__module__code__in=allowed_codes)
                | Q(target_batch__current_module__code__in=allowed_codes)
                | Q(target_herd__module__code__in=allowed_codes)
            )

        qs = qs.order_by("-treatment_date", "-created_at")
        return Response(self.get_serializer(qs, many=True).data)

    @staticmethod
    def _resolve_target_module(treatment):
        """Тот же resolve что в apply_treatment — модуль куда применили."""
        if treatment.target_block_id and treatment.target_block.module_id:
            return treatment.target_block.module
        if treatment.target_batch_id and treatment.target_batch.current_module_id:
            return treatment.target_batch.current_module
        if treatment.target_herd_id and treatment.target_herd.module_id:
            return treatment.target_herd.module
        return None

    @staticmethod
    def _notify_target_module(treatment, result) -> None:
        """TG-уведомление менеджерам модуля-цели после apply."""
        target_module = VetTreatmentLogViewSet._resolve_target_module(treatment)
        if target_module is None:
            return
        try:
            from apps.tgbot.tasks import notify_admins_task
        except Exception:
            return

        drug_name = (
            treatment.drug.nomenclature.name
            if treatment.drug_id and treatment.drug.nomenclature_id
            else "—"
        )
        target_label = (
            f"партия {treatment.target_batch.doc_number}"
            if treatment.target_batch_id
            else (
                f"стадо {treatment.target_herd.doc_number}"
                if treatment.target_herd_id
                else "—"
            )
        )
        withdrawal = (
            f"\nКаренция до {result.new_withdrawal_end.isoformat()}"
            if result.new_withdrawal_end
            else ""
        )
        text = (
            f"🩺 Ветобработка в модуле {target_module.name}\n"
            f"{target_label}\n"
            f"Препарат: {drug_name} ({treatment.dose_quantity} {treatment.unit.code})"
            f"{withdrawal}\n\n"
            f"Подтвердить можно в разделе модуля «Входящие ветобработки»."
        )
        try:
            notify_admins_task.delay(
                text=text,
                organization_id=str(treatment.organization_id),
                module_code=target_module.code,
            )
        except Exception:
            # Бот/celery недоступен — не валим apply
            pass

    @action(detail=False, methods=["get"])
    def timeline(self, request):
        """GET /api/vet/treatments/timeline/?batch=<uuid>  или ?herd=<uuid>

        Возвращает все лечения партии/стада в хронологическом порядке.
        """
        batch_id = request.query_params.get("batch")
        herd_id = request.query_params.get("herd")
        if not batch_id and not herd_id:
            raise DRFValidationError(
                {"__all__": "Укажите ?batch=<uuid> или ?herd=<uuid>."}
            )
        qs = self.get_queryset()
        if batch_id:
            qs = qs.filter(target_batch_id=batch_id)
        if herd_id:
            qs = qs.filter(target_herd_id=herd_id)
        qs = qs.order_by("treatment_date", "created_at")
        data = self.get_serializer(qs, many=True).data
        return Response(data)


class VetAccessoryViewSet(OrgScopedModelViewSet):
    """
    /api/vet/accessories/ — товары для перепродажи через вет-аптеку
    (миски, поилки, переноски и т.п.).

    CRUD по самому товару (карточка). Изменение остатка — только через
    `POST /{id}/receive/` (приём с пересчётом avg-cost) или продажу через
    SaleOrder (auto-decrement в confirm_sale).

    Барkод авто-генерится при create если не задан вручную.
    """

    serializer_class = VetAccessorySerializer
    queryset = VetAccessory.objects.select_related(
        "nomenclature", "nomenclature__unit", "warehouse",
    )
    module_code = "vet"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["warehouse", "is_active"]
    search_fields = ["nomenclature__sku", "nomenclature__name", "barcode", "notes"]
    ordering = ["nomenclature__sku"]

    def perform_create(self, serializer):
        from apps.audit.models import AuditLog
        from apps.warehouses.models import StockMovement
        from apps.warehouses.services.balance import compute_warehouse_balance_for_sku
        from rest_framework.exceptions import ValidationError as DRFValidationError

        nomenclature = serializer.validated_data["nomenclature"]
        warehouse = serializer.validated_data["warehouse"]

        # Склад — единственный источник истины: создавать карточку аксессуара
        # можно только если на этом складе уже есть приход по SKU (через
        # ручное /stock движение или PO.confirm). Без этого инвариант
        # «склад → vet» нарушается — карточка появляется без backing inventory.
        on_hand = compute_warehouse_balance_for_sku(warehouse, nomenclature)
        if on_hand <= 0:
            raise DRFValidationError({
                "warehouse": (
                    f"На складе «{warehouse.code}» нет остатка по SKU "
                    f"«{nomenclature.sku}». Сначала оприходуйте товар через "
                    f"/stock → «+ Приход» или через закуп (/purchases), "
                    f"потом создавайте карточку аксессуара."
                ),
            })

        kwargs = self._save_kwargs_for_create(serializer)

        # Себестоимость авто-подтягиваем из последнего INCOMING на этом
        # складе по этому SKU — оператор уже указал unit_price при приёмке
        # в /stock или PO. Без этого пришлось бы вводить цену дважды.
        # Frontend не отправляет cost_per_unit_uzs при create.
        if not serializer.validated_data.get("cost_per_unit_uzs"):
            last_in = (
                StockMovement.objects
                .filter(
                    organization=warehouse.organization,
                    warehouse_to=warehouse,
                    nomenclature=nomenclature,
                    kind=StockMovement.Kind.INCOMING,
                )
                .order_by("-date", "-created_at")
                .values_list("unit_price_uzs", flat=True)
                .first()
            )
            if last_in is not None:
                kwargs["cost_per_unit_uzs"] = last_in

        # Auto-barcode если пользователь не задал. Формат:
        # `VET-A-{sku}-{rand4}` уникален в рамках org.
        if not serializer.validated_data.get("barcode"):
            sku = nomenclature.sku.upper()[:16]
            kwargs["barcode"] = f"VET-A-{sku}-{secrets.token_hex(2).upper()}"
        instance = serializer.save(**kwargs)
        self._write_audit(AuditLog.Action.CREATE, instance)

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        """POST /api/vet/accessories/{id}/receive/

        Body: {
            "quantity": "10.000",              # required, > 0
            "unit_cost_uzs": "15000.00",       # optional; пересчёт weighted-avg
            "notes": "довоз из китая"          # optional
        }
        """
        from decimal import Decimal

        accessory = self.get_object()
        try:
            qty = Decimal(str(request.data.get("quantity")))
        except Exception:
            raise DRFValidationError({"quantity": "Некорректное количество."})

        unit_cost = request.data.get("unit_cost_uzs")
        unit_cost_dec = None
        if unit_cost not in (None, ""):
            try:
                unit_cost_dec = Decimal(str(unit_cost))
            except Exception:
                raise DRFValidationError(
                    {"unit_cost_uzs": "Некорректная цена."}
                )

        try:
            result = receive_vet_accessory(
                accessory,
                quantity=qty,
                unit_cost_uzs=unit_cost_dec,
                user=request.user,
                notes=request.data.get("notes", ""),
            )
        except VetAccessoryReceiveError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        accessory.refresh_from_db()
        data = self.get_serializer(accessory).data
        data["_result"] = {
            "stock_movement_doc": result.stock_movement.doc_number,
            "previous_cost_uzs": str(result.previous_cost_uzs),
            "new_cost_uzs": str(result.new_cost_uzs),
        }
        return Response(data)


class SellerDeviceTokenViewSet(OrgScopedModelViewSet):
    """
    /api/vet/seller-tokens/ — управление токенами продавцов (admin only).

    POST: создаёт токен для user, генерирует raw token (показывается ОДИН раз
    в ответе на create — потом masked_token).
    POST /{id}/revoke/: помечает revoked_at.
    """

    serializer_class = SellerDeviceTokenSerializer
    queryset = SellerDeviceToken.objects.select_related("user", "organization")
    module_code = "vet"
    write_level = "admin"  # только админ модуля может управлять токенами
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["is_active", "user"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return SellerDeviceTokenCreateSerializer
        return SellerDeviceTokenSerializer

    def perform_create(self, serializer):
        from apps.audit.models import AuditLog

        org = self.request.organization
        # Генерируем raw token
        raw = secrets.token_urlsafe(32)
        instance = serializer.save(
            organization=org,
            token=raw,
            is_active=True,
            created_by=self.request.user if self.request.user.is_authenticated else None,
        )
        self._write_audit(AuditLog.Action.CREATE, instance)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        """POST /api/vet/seller-tokens/{id}/revoke/"""
        from django.utils import timezone
        from apps.audit.models import AuditLog

        tok = self.get_object()
        if tok.revoked_at is not None:
            return Response(
                {"detail": "Токен уже отозван."},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )
        tok.revoked_at = timezone.now()
        tok.is_active = False
        tok.revoked_by = request.user
        tok.save(update_fields=["revoked_at", "is_active", "revoked_by", "updated_at"])
        self._write_audit(
            AuditLog.Action.UPDATE,
            tok,
            verb=f"revoked seller token {tok.masked_token} for {tok.user}",
        )
        return Response(SellerDeviceTokenSerializer(tok).data)
