from __future__ import annotations

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.viewsets import OrganizationContextMixin

from .models import TgLink, TgLinkToken
from .serializers import (
    TgLinkSerializer,
    TgLinkTokenCreateSerializer,
    TgLinkTokenSerializer,
)
from .tasks import handle_tg_update_task, send_debt_reminder_task


class TelegramWebhookView(APIView):
    """
    POST /api/tg/webhook/
    Принимает Telegram updates. Защита через X-Telegram-Bot-Api-Secret-Token.
    """
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        expected = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
        if expected and secret != expected:
            return Response({"ok": False}, status=status.HTTP_403_FORBIDDEN)
        handle_tg_update_task.delay(request.data)
        return Response({"ok": True})


class TgLinkTokenView(OrganizationContextMixin, APIView):
    """
    POST /api/tg/link-token/
    Генерирует одноразовый токен для привязки TG.
    Для пользователя — self.request.user.
    Для контрагента — передать counterparty (UUID) в теле запроса.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TgLinkTokenCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = request.organization

        counterparty_id = serializer.validated_data.get("counterparty")
        counterparty = None
        if counterparty_id:
            from apps.counterparties.models import Counterparty
            try:
                counterparty = Counterparty.objects.get(
                    id=counterparty_id, organization=org
                )
            except Counterparty.DoesNotExist:
                return Response(
                    {"counterparty": "Контрагент не найден."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        token = TgLinkToken.objects.create(
            organization=org,
            user=request.user if not counterparty else None,
            counterparty=counterparty,
        )
        return Response(TgLinkTokenSerializer(token).data, status=status.HTTP_201_CREATED)


class TgMyLinkView(OrganizationContextMixin, APIView):
    """
    GET  /api/tg/links/me/ — текущая привязка текущего пользователя
    DELETE /api/tg/links/me/ — отвязать
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        link = TgLink.objects.filter(
            organization=request.organization,
            user=request.user,
            is_active=True,
        ).first()
        if not link:
            return Response(None)
        return Response(TgLinkSerializer(link).data)

    def delete(self, request):
        TgLink.objects.filter(
            organization=request.organization,
            user=request.user,
        ).update(is_active=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TgCounterpartyLinkView(OrganizationContextMixin, APIView):
    """
    GET  /api/tg/links/counterparty/<uuid>/ — привязка конкретного контрагента
    DELETE /api/tg/links/counterparty/<uuid>/ — отвязать
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        link = TgLink.objects.filter(
            organization=request.organization,
            counterparty_id=pk,
            is_active=True,
        ).first()
        if not link:
            return Response(None)
        return Response(TgLinkSerializer(link).data)

    def delete(self, request, pk):
        TgLink.objects.filter(
            organization=request.organization,
            counterparty_id=pk,
        ).update(is_active=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SendDebtReminderView(OrganizationContextMixin, APIView):
    """
    POST /api/tg/send-debt-reminder/
    Body: {"sale_order_id": "<uuid>"}
    Ручная отправка напоминания должнику.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sale_order_id = request.data.get("sale_order_id")
        if not sale_order_id:
            return Response(
                {"sale_order_id": "Обязательное поле."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = send_debt_reminder_task.delay(str(sale_order_id))
        return Response({"task_id": result.id, "queued": True})
