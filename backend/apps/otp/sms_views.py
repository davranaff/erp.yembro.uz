"""
SMS-функционал общего назначения (не OTP).

Эндпоинты:
  POST /api/sms/send/           — ручная/программная отправка SMS.
  GET  /api/sms/messages/       — журнал отправок с фильтрами.
  GET  /api/sms/balance/        — баланс аккаунта Eskiz.
  POST /api/sms/callback/<sec>/ — webhook от Eskiz по доставке.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache
from rest_framework import filters, generics, status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SmsMessage
from .serializers import SmsMessageSerializer, SmsSendSerializer
from .services import PhoneError, normalize_phone, send_sms
from .services.eskiz import EskizConfigError, EskizError, get_eskiz_client
from .services.sender import update_status_from_callback

logger = logging.getLogger(__name__)


class SmsSendView(APIView):
    """
    POST /api/sms/send/  body: {phone, message, purpose?}

    Доступ — только staff/admin: реальные деньги ходят, не даём массовому юзеру.
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = SmsSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            phone = normalize_phone(serializer.validated_data["phone"])
        except PhoneError as exc:
            return Response(
                {"phone": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            sms = send_sms(
                phone=phone,
                message=serializer.validated_data["message"],
                source=SmsMessage.Source.MANUAL,
                purpose=serializer.validated_data.get("purpose", ""),
                created_by=request.user,
            )
        except EskizConfigError as exc:
            logger.error("sms send: Eskiz не настроен — %s", exc)
            return Response(
                {"detail": "SMS-провайдер не настроен.",
                 "code": "sms_not_configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except EskizError as exc:
            logger.exception("sms send: Eskiz отказал — %s", exc)
            return Response(
                {"detail": "Не удалось отправить SMS, попробуйте позже.",
                 "code": "sms_send_failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(SmsMessageSerializer(sms).data, status=status.HTTP_201_CREATED)


class SmsListView(generics.ListAPIView):
    """
    GET /api/sms/messages/?phone=&status=&source=&search=

    Журнал отправок с пагинацией. Только staff (PII).
    """

    permission_classes = [IsAdminUser]
    serializer_class = SmsMessageSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ("phone", "provider_message_id", "message", "purpose")

    def get_queryset(self):
        qs = SmsMessage.objects.all()
        params = self.request.query_params
        phone = params.get("phone")
        if phone:
            qs = qs.filter(phone__icontains=phone.lstrip("+"))
        status_ = params.get("status")
        if status_:
            qs = qs.filter(status=status_)
        source = params.get("source")
        if source:
            qs = qs.filter(source=source)
        return qs


class SmsBalanceView(APIView):
    """
    GET /api/sms/balance/ → {"balance": int, "currency": "UZS"}

    Кешируем 60 сек, чтобы dashboard не дёргал Eskiz каждый рефреш.
    """

    permission_classes = [IsAuthenticated]
    _CACHE_KEY = "sms:eskiz:balance"
    _CACHE_TTL = 60

    def get(self, request):
        cached = cache.get(self._CACHE_KEY)
        if cached is not None:
            return Response({"balance": cached, "currency": "UZS", "cached": True})

        try:
            client = get_eskiz_client()
            balance = client.get_balance()
        except EskizConfigError:
            return Response(
                {"detail": "SMS-провайдер не настроен.",
                 "code": "sms_not_configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except EskizError as exc:
            logger.exception("sms balance: Eskiz отказал — %s", exc)
            return Response(
                {"detail": "Не удалось получить баланс.",
                 "code": "sms_balance_failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        cache.set(self._CACHE_KEY, balance, self._CACHE_TTL)
        return Response({"balance": balance, "currency": "UZS", "cached": False})


class SmsCallbackView(APIView):
    """
    POST /api/sms/callback/<secret>/

    Webhook от Eskiz: приходит после каждого изменения статуса доставки.
    Авторизация по `secret` в URL (он же в `ESKIZ_CALLBACK_URL`-настройке),
    так что Eskiz сам кладёт его в HTTP-вызов.

    Формат payload (по докам Eskiz):
        {
            "message_id": "...",        # внутренний id у них
            "user_sms_id": "...",
            "country": "uz",
            "phone_number": "998...",
            "sms_count": "1",
            "status_date": "2026-05-12 12:17:43",
            "status": "DELIVRD"         # или EXPIRED/REJECTED/UNDELIV
        }
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, secret: str):
        expected = getattr(settings, "ESKIZ_CALLBACK_SECRET", "") or ""
        if not expected:
            logger.warning("sms callback: ESKIZ_CALLBACK_SECRET не настроен — отбрасываем")
            return Response(status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if secret != expected:
            logger.warning("sms callback: неверный secret — отбрасываем")
            return Response(status=status.HTTP_403_FORBIDDEN)

        payload = request.data if isinstance(request.data, dict) else {}
        message_id = (
            payload.get("message_id")
            or payload.get("request_id")
            or payload.get("id")
        )
        delivery_status = (payload.get("status") or "").strip()
        if not message_id or not delivery_status:
            return Response(
                {"detail": "message_id / status обязательны."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sms = update_status_from_callback(
            provider_message_id=str(message_id),
            status=delivery_status,
            status_date=payload.get("status_date"),
            raw_payload=payload,
        )
        if sms is None:
            # 200 чтобы Eskiz не ретраил вечно — нашего id у нас нет.
            return Response({"ok": True, "matched": False})
        return Response({"ok": True, "matched": True, "status": sms.status})
