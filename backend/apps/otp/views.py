from __future__ import annotations

import logging

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .serializers import OtpRequestSerializer, OtpVerifySerializer
from .services import (
    OtpError,
    PhoneError,
    normalize_phone,
    request_otp,
    verify_otp,
)
from .services.eskiz import EskizConfigError, EskizError

logger = logging.getLogger(__name__)


class OtpRequestThrottle(AnonRateThrottle):
    """IP-throttle для resend-кнопки — защита от ботов и циклов в UI.

    Rate из settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['otp-request'].
    """
    scope = "otp-request"


class OtpVerifyThrottle(AnonRateThrottle):
    scope = "otp-verify"


def _client_ip(request) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class OtpRequestView(APIView):
    """
    POST /api/otp/request/
    body: {phone, purpose}
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OtpRequestThrottle]

    def post(self, request):
        serializer = OtpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            phone = normalize_phone(serializer.validated_data["phone"])
        except PhoneError as exc:
            return Response(
                {"phone": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST
            )

        # Клиентский шаблон принимаем только если включён ENV-флаг,
        # иначе игнорируем — иначе можно превратить наш OTP-канал в
        # spam-шлюз "напиши кому угодно что угодно".
        template = None
        if getattr(settings, "OTP_ALLOW_CLIENT_TEMPLATE", False):
            template = serializer.validated_data.get("message_template")

        try:
            result = request_otp(
                phone=phone,
                purpose=serializer.validated_data["purpose"],
                requested_ip=_client_ip(request),
                message_template=template,
            )
        except OtpError as exc:
            body = {"detail": str(exc), "code": exc.code}
            if hasattr(exc, "retry_after"):
                body["retry_after"] = exc.retry_after
            return Response(body, status=exc.status)
        except EskizConfigError as exc:
            logger.error("OTP: Eskiz не настроен — %s", exc)
            return Response(
                {"detail": "SMS-провайдер не настроен.",
                 "code": "sms_not_configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except EskizError as exc:
            logger.exception("OTP: Eskiz отказал — %s", exc)
            return Response(
                {"detail": "Не удалось отправить SMS, попробуйте позже.",
                 "code": "sms_send_failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "ok": True,
                "phone": phone,
                "expires_at": result.expires_at,
                "resend_available_at": result.resend_available_at,
            },
            status=status.HTTP_200_OK,
        )


class OtpVerifyView(APIView):
    """
    POST /api/otp/verify/
    body: {phone, purpose, code}

    Возвращает {ok: true, phone, purpose}. Этот endpoint только подтверждает
    код — выдача JWT / привязка к user'у делается отдельным шагом, который
    добавится по мере подключения OTP к login/registration-флоу.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OtpVerifyThrottle]

    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            phone = normalize_phone(serializer.validated_data["phone"])
        except PhoneError as exc:
            return Response(
                {"phone": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            verify_otp(
                phone=phone,
                purpose=serializer.validated_data["purpose"],
                code=serializer.validated_data["code"],
            )
        except OtpError as exc:
            return Response(
                {"detail": str(exc), "code": exc.code}, status=exc.status,
            )

        return Response(
            {
                "ok": True,
                "phone": phone,
                "purpose": serializer.validated_data["purpose"],
            },
            status=status.HTTP_200_OK,
        )
