"""
Public-эндпоинты вет.аптеки для розничного сканера.

Анонимный read /api/vet/public/scan/<barcode>/ — данные лота без чувствительной
информации (organization, supplier, purchase). Может открыть любой человек.

Bearer-only POST /api/vet/public/sell/ — продажа лота через токен продавца.
Bearer-only GET /api/vet/public/customers/ — список покупателей орги для
выпадающего списка в форме продажи (опциональная привязка клиента).
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, views
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from apps.counterparties.models import Counterparty

from .authentication import SellerTokenAuthentication
from .models import VetAccessory, VetStockBatch
from .serializers import VetAccessoryPublicSerializer, VetStockBatchPublicSerializer
from .services.sell import VetSellError, sell_vet_stock
from .services.sell_accessory import VetAccessorySellError, sell_vet_accessory


# Префикс в SaleOrder.notes для записи и поиска idempotency-token.
# Без отдельной модели/кэша — хранится прямо в notes.
_IDEMPOTENCY_PREFIX = "idempotency_key="
_IDEMPOTENCY_WINDOW_MIN = 30


def _find_idempotent_sale(organization, idempotency_key: str):
    """Найти уже созданный SaleOrder с этим idempotency-ключом
    за последние 30 минут. None если не найден."""
    from apps.sales.models import SaleOrder
    if not idempotency_key:
        return None
    cutoff = timezone.now() - timedelta(minutes=_IDEMPOTENCY_WINDOW_MIN)
    needle = f"{_IDEMPOTENCY_PREFIX}{idempotency_key}"
    return (
        SaleOrder.objects
        .filter(
            organization=organization,
            notes__contains=needle,
            created_at__gte=cutoff,
        )
        .order_by("-created_at")
        .first()
    )


def _annotate_idempotency(sale_order, idempotency_key: str) -> None:
    """Дописать idempotency_key в SaleOrder.notes для будущего dedup."""
    if not idempotency_key:
        return
    marker = f"{_IDEMPOTENCY_PREFIX}{idempotency_key}"
    if sale_order.notes and marker in sale_order.notes:
        return
    sale_order.notes = (
        (sale_order.notes or "") + f"\n{marker}"
    ).strip()
    sale_order.save(update_fields=["notes", "updated_at"])


def _serialize_existing_sale(sale_order) -> dict:
    """Свернуть существующий SaleOrder в payload, идентичный возвращаемому
    свежим успешным sell-ом. Используется при idempotent retry."""
    return {
        "source_kind": "idempotent_replay",
        "sale_order_id": str(sale_order.id),
        "sale_order_doc": sale_order.doc_number,
        "total_uzs": str(sale_order.amount_uzs or "0"),
        "customer_id": str(sale_order.customer_id) if sale_order.customer_id else None,
        "customer_name": sale_order.customer.name if sale_order.customer_id else None,
    }


class VetPublicScanView(views.APIView):
    """
    GET /api/vet/public/scan/<barcode>/

    Анонимный доступ для кросс-орг просмотра. Если в Authorization есть
    валидный Bearer seller-token — добавляем «приватные» поля для
    продавца (себестоимость, рекомендуемая цена). Без токена — публичный
    минимум, чтобы случайный посетитель не видел маржу.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # auth делаем вручную (см. _try_seller_auth)

    def _try_seller_auth(self, request) -> bool:
        """Тихая попытка авторизоваться как продавец.

        Возвращает True если Bearer-токен валиден. Невалидный/отсутствующий
        токен → False (без 401), чтобы анонимный пользователь мог смотреть
        публичную карточку без авторизации.
        """
        from .models import SellerDeviceToken

        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            return False
        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != "Bearer":
            return False
        try:
            tok = SellerDeviceToken.objects.get(token=parts[1])
        except SellerDeviceToken.DoesNotExist:
            return False
        if not tok.is_active or tok.revoked_at is not None:
            return False
        return True

    def get(self, request, barcode: str):
        # Поиск без фильтра по organization — barcode уникален в рамках org,
        # но мы хотим работать кросс-орг для public. Порядок поиска:
        #   1. VetStockBatch (лот препарата)
        #   2. VetAccessory (аксессуар)
        #   3. FeedBagLot (партия фасованного корма)
        batch = (
            VetStockBatch.objects
            .select_related("drug__nomenclature", "unit")
            .filter(barcode=barcode)
            .first()
        )
        if batch is not None:
            data = VetStockBatchPublicSerializer(batch).data
            data["source_kind"] = "drug_lot"
            return Response(data)

        accessory = (
            VetAccessory.objects
            .select_related("nomenclature", "nomenclature__unit")
            .filter(barcode=barcode)
            .first()
        )
        if accessory is not None:
            data = VetAccessoryPublicSerializer(accessory).data
            data["source_kind"] = "accessory"
            return Response(data)

        # FeedBagLot — фасованный корм (партия мешков).
        from apps.feed.models import FeedBagLot

        bag_lot = (
            FeedBagLot.objects
            .select_related(
                "recipe_version__recipe",
                "source_feed_batch",
                "storage_warehouse",
            )
            .filter(barcode=barcode)
            .first()
        )
        if bag_lot is not None:
            recipe = bag_lot.recipe_version.recipe
            from decimal import Decimal as _D
            data = {
                "source_kind": "feed_bag_lot",
                "id": str(bag_lot.id),
                "doc_number": bag_lot.doc_number,
                "barcode": bag_lot.barcode,
                "status": bag_lot.status,
                "drug_name": f"{recipe.code} · {recipe.name}",
                "lot_number": bag_lot.doc_number,
                "bag_weight_kg": str(bag_lot.bag_weight_kg),
                "bags_initial": bag_lot.bags_initial,
                "bags_remaining": bag_lot.bags_remaining,
                "current_quantity": str(bag_lot.bags_remaining),
                "unit_code": "qop",
                "is_medicated": bag_lot.is_medicated,
                "withdrawal_period_days": bag_lot.withdrawal_period_days,
                "withdrawal_period_ends": (
                    bag_lot.withdrawal_period_ends.isoformat()
                    if bag_lot.withdrawal_period_ends else None
                ),
                "packaged_at": bag_lot.packaged_at.isoformat(),
                "warehouse_code": (
                    bag_lot.storage_warehouse.code
                    if bag_lot.storage_warehouse_id else None
                ),
            }
            # Приватные поля: видны только если запрос пришёл с валидным
            # seller-токеном. Без этого любой посетитель увидел бы
            # внутреннюю себестоимость.
            if self._try_seller_auth(request):
                cost = _D(bag_lot.unit_cost_uzs or 0)
                # Рекомендованная розничная цена = себестоимость × 1.30
                # (30% маржа). Это hint для продавца, можно перебить вручную.
                suggested = (cost * _D("1.30")).quantize(_D("1"))
                bags_remaining = _D(bag_lot.bags_remaining or 0)
                bag_weight = _D(bag_lot.bag_weight_kg or 0)
                data.update({
                    "unit_cost_uzs": str(cost),
                    "suggested_price_uzs": str(suggested),
                    "total_remaining_kg": str(bags_remaining * bag_weight),
                    "recipe_code": recipe.code,
                    "recipe_name": recipe.name,
                })
            return Response(data)

        return Response(
            {"detail": "Товар с таким штрих-кодом не найден."},
            status=status.HTTP_404_NOT_FOUND,
        )


class VetPublicSellView(views.APIView):
    """
    POST /api/vet/public/sell/

    Body: {
        "barcode": str,
        "quantity": str,
        "unit_price_uzs": str | null,
        "customer_id": str | null,   # опционально: id Counterparty
    }

    Требует Bearer-токен продавца (SellerDeviceToken).
    Если `customer_id` не передан — продажа закрепляется на «Розничный покупатель»
    (создаётся при необходимости).
    """

    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SellerTokenAuthentication]

    def post(self, request):
        barcode = request.data.get("barcode")
        qty_raw = request.data.get("quantity")
        if not barcode or not qty_raw:
            raise DRFValidationError(
                {"__all__": "Укажите barcode и quantity."}
            )

        try:
            qty = Decimal(str(qty_raw))
        except Exception:
            raise DRFValidationError({"quantity": "Неверное число."})
        if qty <= 0:
            raise DRFValidationError(
                {"quantity": "Количество должно быть > 0."}
            )

        # Idempotency: на mobile-сканере network glitch + auto-retry легко
        # отправляет POST дважды → создавались два SaleOrder + двойная JE
        # на один отсканированный товар. Клиенту рекомендуется отправлять
        # Idempotency-Key header (UUID на каждое нажатие SELL); если он
        # задан, мы ищем существующий SaleOrder с этим ключом в notes и
        # возвращаем результат прошлого вызова.
        idempotency_key = (
            request.META.get("HTTP_IDEMPOTENCY_KEY") or ""
        ).strip()

        unit_price_raw = request.data.get("unit_price_uzs")
        unit_price = None
        if unit_price_raw not in (None, ""):
            try:
                unit_price = Decimal(str(unit_price_raw))
            except Exception:
                raise DRFValidationError({"unit_price_uzs": "Неверное число."})

        # organization прикрепляется в SellerTokenAuthentication
        organization = getattr(request, "organization", None)
        if organization is None:
            raise DRFValidationError({"__all__": "Не определена организация токена."})

        # Idempotency lookup: если этот ключ уже встречался — вернём
        # тот же SaleOrder без повторной продажи.
        existing_sale = _find_idempotent_sale(organization, idempotency_key)
        if existing_sale is not None:
            return Response(
                _serialize_existing_sale(existing_sale),
                status=status.HTTP_200_OK,
            )

        # Опциональный явный клиент. Если не задан — sell_vet_stock сам
        # фолбекнется на «Розничный покупатель».
        customer = None
        customer_id = request.data.get("customer_id")
        if customer_id:
            customer = (
                Counterparty.objects
                .filter(organization=organization, id=customer_id)
                .exclude(kind=Counterparty.Kind.SUPPLIER)
                .first()
            )
            if customer is None:
                raise DRFValidationError({
                    "customer_id": "Клиент не найден в организации токена.",
                })

        # Сначала ищем препарат-лот, если не нашли — аксессуар.
        batch = (
            VetStockBatch.objects
            .filter(organization=organization, barcode=barcode)
            .first()
        )
        if batch is not None:
            try:
                result = sell_vet_stock(
                    stock_batch=batch,
                    quantity=qty,
                    seller_user=request.user,
                    organization=organization,
                    customer=customer,
                    unit_price_uzs=unit_price,
                )
            except VetSellError as exc:
                raise DRFValidationError(
                    exc.message_dict if hasattr(exc, "message_dict") else exc.messages
                )
            _annotate_idempotency(result.sale_order, idempotency_key)
            return Response({
                "source_kind": "drug_lot",
                "sale_order_id": str(result.sale_order.id),
                "sale_order_doc": result.sale_order.doc_number,
                "total_uzs": str(result.total_uzs),
                "remaining_qty": str(result.remaining_qty),
                "lot_status": result.stock_batch.status,
                "customer_id": str(result.sale_order.customer_id),
                "customer_name": result.sale_order.customer.name,
            }, status=status.HTTP_201_CREATED)

        accessory = (
            VetAccessory.objects
            .filter(organization=organization, barcode=barcode)
            .first()
        )
        if accessory is not None:
            try:
                result = sell_vet_accessory(
                    accessory=accessory,
                    quantity=qty,
                    seller_user=request.user,
                    organization=organization,
                    customer=customer,
                    unit_price_uzs=unit_price,
                )
            except VetAccessorySellError as exc:
                raise DRFValidationError(
                    exc.message_dict if hasattr(exc, "message_dict") else exc.messages
                )
            _annotate_idempotency(result.sale_order, idempotency_key)
            return Response({
                "source_kind": "accessory",
                "sale_order_id": str(result.sale_order.id),
                "sale_order_doc": result.sale_order.doc_number,
                "total_uzs": str(result.total_uzs),
                "remaining_qty": str(result.remaining_qty),
                "customer_id": str(result.sale_order.customer_id),
                "customer_name": result.sale_order.customer.name,
            }, status=status.HTTP_201_CREATED)

        # FeedBagLot — фасованный корм. Тот же public-flow, отдельный сервис
        # потому что quantity = шт мешков, нет дефолтной отпускной цены,
        # и SaleItem.feed_bag_lot пишется в свой собственный FK.
        from apps.feed.models import FeedBagLot
        from apps.feed.services.sell_feed_bag import (
            FeedBagSellError,
            sell_feed_bag_lot,
        )

        bag_lot = (
            FeedBagLot.objects
            .filter(organization=organization, barcode=barcode)
            .first()
        )
        if bag_lot is not None:
            try:
                result = sell_feed_bag_lot(
                    bag_lot=bag_lot,
                    quantity=qty,
                    seller_user=request.user,
                    organization=organization,
                    customer=customer,
                    unit_price_uzs=unit_price,
                )
            except FeedBagSellError as exc:
                raise DRFValidationError(
                    exc.message_dict if hasattr(exc, "message_dict") else exc.messages
                )
            _annotate_idempotency(result.sale_order, idempotency_key)
            return Response({
                "source_kind": "feed_bag_lot",
                "sale_order_id": str(result.sale_order.id),
                "sale_order_doc": result.sale_order.doc_number,
                "total_uzs": str(result.total_uzs),
                "remaining_qty": str(result.remaining_bags),
                "lot_status": result.bag_lot.status,
                "customer_id": str(result.sale_order.customer_id),
                "customer_name": result.sale_order.customer.name,
            }, status=status.HTTP_201_CREATED)

        raise DRFValidationError(
            {"barcode": "Товар не найден в организации токена."}
        )


class VetPublicCustomersView(views.APIView):
    """
    GET /api/vet/public/customers/

    Список покупателей (не-supplier) орги для выпадающего списка в форме
    продажи на /scan/<barcode>. Bearer-токен продавца обязателен.
    """

    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SellerTokenAuthentication]

    def get(self, request):
        organization = getattr(request, "organization", None)
        if organization is None:
            raise DRFValidationError({"__all__": "Не определена организация токена."})
        qs = (
            Counterparty.objects
            .filter(organization=organization)
            .exclude(kind=Counterparty.Kind.SUPPLIER)
            .order_by("name")
            .values("id", "code", "name", "kind")[:200]
        )
        return Response([
            {"id": str(c["id"]), "code": c["code"], "name": c["name"], "kind": c["kind"]}
            for c in qs
        ])
