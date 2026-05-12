"""
GET /api/notifications/ — объединённый список SMS + TG для UI «История оповещений».

Это not REST-list по одной модели, а склейка двух журналов:
  - apps.otp.SmsMessage
  - apps.tgbot.TgMessage

Запросы сериализуем в общую структуру с полем `channel`, фильтр по
counterparty/channel/source/status/period, простой limit-offset.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from django.utils.dateparse import parse_datetime
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tgbot.models import TgMessage

from .models import SmsMessage


def _sms_to_dict(sms: SmsMessage) -> dict:
    return {
        "channel": "sms",
        "id": str(sms.id),
        "created_at": sms.created_at.isoformat(),
        "phone": sms.phone,
        "chat_id": None,
        "counterparty_id": None,
        "counterparty_name": None,
        "source": sms.source,
        "purpose": sms.purpose,
        "text": sms.message,
        "status": sms.status,
        "error_msg": sms.error_msg,
        "provider_message_id": sms.provider_message_id,
        "sent_at": sms.sent_at.isoformat() if sms.sent_at else None,
        "delivered_at": sms.delivered_at.isoformat() if sms.delivered_at else None,
    }


def _tg_to_dict(tg: TgMessage) -> dict:
    return {
        "channel": "tg",
        "id": str(tg.id),
        "created_at": tg.created_at.isoformat(),
        "phone": None,
        "chat_id": tg.chat_id,
        "counterparty_id": str(tg.counterparty_id) if tg.counterparty_id else None,
        "counterparty_name": tg.counterparty.name if tg.counterparty_id else None,
        "source": tg.source,
        "purpose": "",
        "text": tg.text,
        "status": tg.status,
        "error_msg": tg.error_msg,
        "provider_message_id": "",
        "sent_at": tg.sent_at.isoformat() if tg.sent_at else None,
        "delivered_at": None,
    }


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    return parse_datetime(s)


class NotificationsListView(APIView):
    """
    GET /api/notifications/
      ?channel=sms|tg
      &counterparty=<uuid>
      &source=<value>
      &status=<value>
      &phone=<digits>
      &from=<iso>&to=<iso>
      &limit=50&offset=0
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        params = request.query_params
        channel = (params.get("channel") or "").lower().strip()
        cp_id = params.get("counterparty")
        source = params.get("source")
        status_ = params.get("status")
        phone = params.get("phone")
        dt_from = _parse_dt(params.get("from"))
        dt_to = _parse_dt(params.get("to"))
        try:
            limit = max(1, min(200, int(params.get("limit") or 50)))
            offset = max(0, int(params.get("offset") or 0))
        except ValueError:
            return Response({"detail": "Invalid limit/offset."}, status=400)

        sms_qs = SmsMessage.objects.all()
        tg_qs = TgMessage.objects.select_related("counterparty").all()

        if cp_id:
            tg_qs = tg_qs.filter(counterparty_id=cp_id)
            # SmsMessage не имеет FK на Counterparty — связываем через phone.
            from apps.counterparties.models import Counterparty
            try:
                cp_phone = (Counterparty.objects.filter(id=cp_id)
                            .values_list("phone", flat=True).first() or "")
            except Exception:
                cp_phone = ""
            if cp_phone:
                # Берём только цифры, ищем substring.
                digits = "".join(c for c in cp_phone if c.isdigit())
                if digits:
                    sms_qs = sms_qs.filter(phone__icontains=digits[-9:])
                else:
                    sms_qs = sms_qs.none()
            else:
                sms_qs = sms_qs.none()
        if source:
            sms_qs = sms_qs.filter(source=source)
            tg_qs = tg_qs.filter(source=source)
        if status_:
            sms_qs = sms_qs.filter(status=status_)
            tg_qs = tg_qs.filter(status=status_)
        if phone:
            sms_qs = sms_qs.filter(phone__icontains=phone.lstrip("+"))
            tg_qs = tg_qs.none()  # у TG нет phone
        if dt_from:
            sms_qs = sms_qs.filter(created_at__gte=dt_from)
            tg_qs = tg_qs.filter(created_at__gte=dt_from)
        if dt_to:
            sms_qs = sms_qs.filter(created_at__lte=dt_to)
            tg_qs = tg_qs.filter(created_at__lte=dt_to)

        if channel == "sms":
            tg_qs = tg_qs.none()
        elif channel == "tg":
            sms_qs = sms_qs.none()

        # Простая склейка: тащим первые (limit+offset) с каждой стороны,
        # объединяем, сортируем по created_at, обрезаем.
        cap = limit + offset
        sms_items = list(sms_qs.order_by("-created_at")[:cap])
        tg_items = list(tg_qs.order_by("-created_at")[:cap])
        merged = (
            [_sms_to_dict(s) for s in sms_items]
            + [_tg_to_dict(t) for t in tg_items]
        )
        merged.sort(key=lambda x: x["created_at"], reverse=True)

        total = sms_qs.count() + tg_qs.count()
        page = merged[offset:offset + limit]
        return Response({
            "results": page,
            "count": total,
            "limit": limit,
            "offset": offset,
        })
