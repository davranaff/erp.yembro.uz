from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.viewsets import OrganizationContextMixin

from .models import TgLink, TgLinkToken
from .serializers import (
    TgLinkSerializer,
    TgLinkTokenCreateSerializer,
    TgLinkTokenSerializer,
)
from .tasks import send_debt_reminder_task


class TelegramWebhookView(APIView):
    """
    POST /api/tg/webhook/
    Принимает Telegram updates. Защита через X-Telegram-Bot-Api-Secret-Token.

    Dispatch отправляется в Celery (`handle_tg_update_task.delay`) — webhook
    возвращает 200 OK моментально. Тяжёлые команды (P&L отчёт, mass batches)
    могут считаться секунды; на синхронной обработке Telegram бы ретраил.
    """
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        expected = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
        if expected and secret != expected:
            return Response({"ok": False}, status=status.HTTP_403_FORBIDDEN)
        try:
            from .tasks import handle_tg_update_task
            handle_tg_update_task.delay(request.data)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("tg webhook enqueue error")
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
    Body: {"sale_order_id": "<uuid>", "text": "<override?>"}

    Ручная отправка напоминания должнику. Если в body есть text — используется
    как есть (оператор отредактировал в превью-модалке), иначе берётся
    стандартный шаблон fmt_debt_reminder_uz.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sale_order_id = request.data.get("sale_order_id")
        if not sale_order_id:
            return Response(
                {"sale_order_id": "Обязательное поле."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        custom_text = (request.data.get("text") or "").strip() or None
        result = send_debt_reminder_task.delay(str(sale_order_id), custom_text)
        return Response({"task_id": result.id, "queued": True})


class MiniAppAuthView(APIView):
    """
    POST /api/tg/miniapp/auth/
    Body: {"init_data": "<raw query string из Telegram.WebApp.initData>"}

    Аутентификация Telegram Mini App. Проверяет HMAC-подпись initData по
    схеме Telegram (secret = HMAC_SHA256("WebAppData", BOT_TOKEN); затем
    HMAC_SHA256(secret, data_check_string) == hash).

    Логика:
      - подпись невалидна или просрочена → 401
      - chat_id не привязан к user-линке (только counterparty или нет линки)
        → 200 {"linked": false}
      - линка найдена → 200 {"linked": true, "access", "refresh", "user",
        "preferred_org": {"code", "name"}}

    Frontend на linked=false редиректит на лендинг.
    """
    permission_classes = []
    authentication_classes = []

    # initData считается просроченным после этого времени (secs). Telegram
    # рекомендует <= 24h; 1h достаточно для Mini App, который запускается
    # пользователем интерактивно.
    INIT_DATA_TTL_SECONDS = 3600

    def post(self, request):
        init_data = request.data.get("init_data") or ""
        if not isinstance(init_data, str) or not init_data:
            return Response(
                {"detail": "init_data is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        if not token:
            return Response(
                {"detail": "Bot is not configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        parsed = self._verify_init_data(init_data, token)
        if parsed is None:
            return Response(
                {"detail": "Invalid init_data signature"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # auth_date — unix timestamp когда Telegram сгенерил initData. Защита
        # от replay: если данные старше TTL — отвергаем.
        try:
            auth_date = int(parsed.get("auth_date", "0"))
        except (TypeError, ValueError):
            auth_date = 0
        from django.utils import timezone

        if not auth_date or (timezone.now().timestamp() - auth_date) > self.INIT_DATA_TTL_SECONDS:
            return Response(
                {"detail": "init_data expired"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            tg_user = json.loads(parsed.get("user", "") or "{}")
        except json.JSONDecodeError:
            tg_user = {}
        chat_id = tg_user.get("id")
        if not isinstance(chat_id, int):
            return Response(
                {"detail": "Telegram user.id missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Counterparty-линки в Mini App не пускаем — только сотрудники с
        # привязанным ERP-юзером.
        link = (
            TgLink.objects.filter(
                chat_id=chat_id,
                user__isnull=False,
                is_active=True,
            )
            .select_related("user", "organization", "active_organization")
            .first()
        )
        if not link or not link.user:
            return Response({"linked": False})

        from apps.users.serializers import MeSerializer

        user = link.user
        refresh = RefreshToken.for_user(user)

        # Предпочтительная организация для Mini App: active_organization
        # (если юзер раньше переключал /org в боте) или org привязки.
        preferred_org = link.active_organization or link.organization

        return Response({
            "linked": True,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": MeSerializer(user).data,
            "preferred_org": {
                "code": preferred_org.code,
                "name": preferred_org.name,
            },
        })

    @classmethod
    def _verify_init_data(cls, init_data: str, bot_token: str) -> dict[str, str] | None:
        """
        Возвращает dict пар, если HMAC валиден, иначе None.

        Алгоритм Telegram (https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app):
            1. Распарсить query string в пары key=value (URL-decoded).
            2. Вынуть `hash`, остальные ключи отсортировать по имени и
               склеить как "key=value\nkey=value\n...".
            3. secret = HMAC_SHA256("WebAppData", bot_token)
            4. expected = HMAC_SHA256(secret, data_check_string).hex()
            5. Сравнить с `hash`.
        """
        # parse_qsl автоматически URL-decode'ит values. keep_blank_values
        # для безопасности (Telegram может слать пустые поля).
        try:
            pairs = dict(parse_qsl(init_data, strict_parsing=True, keep_blank_values=True))
        except ValueError:
            return None

        received_hash = pairs.pop("hash", "")
        if not received_hash:
            return None

        data_check_string = "\n".join(
            f"{k}={pairs[k]}" for k in sorted(pairs.keys())
        )
        secret_key = hmac.new(
            b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256,
        ).digest()
        expected = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, received_hash):
            return None
        return pairs


class PreviewDebtReminderView(OrganizationContextMixin, APIView):
    """
    GET /api/tg/preview-debt-reminder/?sale_order_id=<uuid>

    Возвращает рендеренный текст напоминания (без отправки) — для
    превью-модалки в UI. Оператор может отредактировать и потом
    отправить через send-debt-reminder с body.text.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.sales.models import SaleOrder
        from .models import TgLink
        from .notifications import fmt_debt_reminder_uz

        sale_order_id = request.query_params.get("sale_order_id")
        if not sale_order_id:
            return Response(
                {"sale_order_id": "Обязательное поле."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            order = SaleOrder.objects.select_related(
                "customer", "organization",
            ).get(id=sale_order_id, organization=request.organization)
        except SaleOrder.DoesNotExist:
            return Response(
                {"detail": "Продажа не найдена."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Проверяем что у клиента подключён TG — иначе превью бессмысленно.
        link = TgLink.objects.filter(
            organization=order.organization,
            counterparty=order.customer,
            is_active=True,
        ).first()

        text = fmt_debt_reminder_uz(order, order.customer)
        return Response({
            "text": text,
            "has_tg_link": link is not None,
            "tg_username": link.tg_username if link else None,
            "customer_name": order.customer.name,
            "doc_number": order.doc_number,
        })
