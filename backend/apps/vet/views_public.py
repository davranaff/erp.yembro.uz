"""
Public-эндпоинты вет.аптеки для розничного сканера.

Анонимный read /api/vet/public/scan/<barcode>/ — данные лота без чувствительной
информации (organization, supplier, purchase). Может открыть любой человек.

Bearer-only POST /api/vet/public/sell/ — продажа лота через токен продавца.
"""
from __future__ import annotations

from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, views
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from .authentication import SellerTokenAuthentication
from .models import VetStockBatch
from .serializers import VetStockBatchPublicSerializer
from .services.sell import VetSellError, sell_vet_stock


class VetPublicScanView(views.APIView):
    """
    GET /api/vet/public/scan/<barcode>/

    Анонимно. Возвращает лот по штрих-коду со скрытыми чувствительными
    полями. Если лот в RECALLED/EXPIRED — возвращаем данные но с флагом.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # анонимно

    def get(self, request, barcode: str):
        # Поиск без фильтра по organization — barcode уникален в рамках org,
        # но мы хотим работать кросс-орг для public. Если несколько orgs
        # имеют одинаковый barcode (теоретически возможно из-за per-org
        # уникальности) — берём первый. На практике barcode авто-генерится
        # с case-sensitive токеном, коллизия маловероятна.
        batch = (
            VetStockBatch.objects
            .select_related("drug__nomenclature", "unit")
            .filter(barcode=barcode)
            .first()
        )
        if batch is None:
            return Response(
                {"detail": "Лот с таким штрих-кодом не найден."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(VetStockBatchPublicSerializer(batch).data)


class VetPublicSellView(views.APIView):
    """
    POST /api/vet/public/sell/

    Body: {"barcode": str, "quantity": str, "unit_price_uzs": str | null}

    Требует Bearer-токен продавца (SellerDeviceToken).
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

        batch = (
            VetStockBatch.objects
            .filter(organization=organization, barcode=barcode)
            .first()
        )
        if batch is None:
            raise DRFValidationError(
                {"barcode": "Лот не найден в организации токена."}
            )

        try:
            result = sell_vet_stock(
                stock_batch=batch,
                quantity=qty,
                seller_user=request.user,
                organization=organization,
                customer=None,
                unit_price_uzs=unit_price,
            )
        except VetSellError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        return Response({
            "sale_order_id": str(result.sale_order.id),
            "sale_order_doc": result.sale_order.doc_number,
            "total_uzs": str(result.total_uzs),
            "remaining_qty": str(result.remaining_qty),
            "lot_status": result.stock_batch.status,
        }, status=status.HTTP_201_CREATED)
