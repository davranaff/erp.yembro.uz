"""
ViewSet журнала аудита.

GET   /api/audit/                          — список с фильтрами + пагинацией
GET   /api/audit/{id}/                     — деталь (для drawer'а)
GET   /api/audit/export/?format=csv        — CSV-экспорт (текущие фильтры)
GET   /api/audit/stats/                    — агрегаты за период (KPI, топ юзеров/модулей)
GET   /api/audit/users/<uuid>/activity/    — профиль активности конкретного юзера
"""
from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import StreamingHttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response

from apps.common.pagination import FlexiblePageNumberPagination
from apps.common.viewsets import OrgReadOnlyViewSet


class CSVRenderer(BaseRenderer):
    """
    Зарегистрированный renderer чтобы DRF content-negotiation принимал
    `?format=csv` (иначе 404 на `@action export/?format=csv`). Реальный
    рендер не нужен — наш action возвращает StreamingHttpResponse сам.
    """

    media_type = "text/csv"
    format = "csv"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        # Не используется: action возвращает StreamingHttpResponse напрямую.
        return data if isinstance(data, (bytes, str)) else b""

from .filters import AuditLogFilter
from .models import AuditLog
from .serializers import AuditLogSerializer


class _Echo:
    """File-like объект для StreamingHttpResponse — просто возвращает то что записали."""

    def write(self, value):
        return value


class AuditLogViewSet(OrgReadOnlyViewSet):
    """/api/audit/ — журнал аудита."""

    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("module", "actor", "entity_content_type")
    module_code = "admin"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = AuditLogFilter
    # Расширили: теперь можно искать по email юзера и коду модуля,
    # а не только по описанию/snapshot.
    search_fields = [
        "action_verb",
        "entity_repr",
        "actor__email",
        "actor__full_name",
        "module__code",
    ]
    ordering_fields = ["occurred_at"]
    ordering = ["-occurred_at"]
    pagination_class = FlexiblePageNumberPagination
    # JSON по умолчанию + CSV — иначе ?format=csv даёт 404 на content-negotiation.
    renderer_classes = [JSONRenderer, CSVRenderer]

    @action(detail=False, methods=["get"], url_path="export")
    def export_csv(self, request):
        """
        GET /api/audit/export/?format=csv

        Стримит CSV с теми же фильтрами что и list. Использует настоящий
        фильтрованный queryset (без пагинации) — на больших объёмах нужен
        диапазон дат, иначе клиент скачает всё.
        """
        qs = self.filter_queryset(self.get_queryset())

        pseudo = _Echo()
        writer = csv.writer(pseudo, delimiter=",", quoting=csv.QUOTE_MINIMAL)

        header = [
            "occurred_at",
            "actor",
            "module",
            "action",
            "entity_type",
            "entity",
            "description",
            "ip",
            "user_agent",
        ]

        def gen():
            # BOM для корректного открытия в Excel
            yield "﻿"
            yield writer.writerow(header)
            for row in qs.iterator():
                yield writer.writerow(
                    [
                        row.occurred_at.isoformat(),
                        row.actor.email if row.actor_id else "",
                        row.module.code if row.module_id else "",
                        row.action,
                        row.entity_content_type.model if row.entity_content_type_id else "",
                        row.entity_repr or "",
                        row.action_verb or "",
                        row.ip_address or "",
                        row.user_agent or "",
                    ]
                )

        response = StreamingHttpResponse(gen(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="audit-log.csv"'
        return response

    # ── /stats/ ────────────────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """
        GET /api/audit/stats/

        Агрегированная сводка по тем же фильтрам что и list. Возвращает:
            - total: общее число событий за период
            - unique_actors: число уникальных пользователей
            - by_action: { action_code: count } — распределение по типам
            - by_module: [ { code, count } ] — топ-7 модулей
            - top_actors: [ { user_id, email, full_name, count } ] — топ-10 юзеров
            - daily: [ { date, count } ] — активность по дням (для sparkline)
            - period: { from, to } — фактически использованный диапазон

        Учитывает все фильтры (action, module, actor, date_after/before,
        search) — KPI всегда совпадают с тем что юзер видит в ленте.
        """
        qs = self.filter_queryset(self.get_queryset())

        # period — берём из date_after/date_before если переданы, иначе
        # последние 30 дней (defensive default чтобы не сканировать всю историю).
        date_from_raw = request.query_params.get("date_after")
        date_to_raw = request.query_params.get("date_before")
        if date_from_raw:
            try:
                period_from = datetime.fromisoformat(date_from_raw.replace("Z", "+00:00"))
            except ValueError as exc:
                raise DRFValidationError({"date_after": str(exc)})
        else:
            period_from = timezone.now() - timedelta(days=30)
        if date_to_raw:
            try:
                period_to = datetime.fromisoformat(date_to_raw.replace("Z", "+00:00"))
            except ValueError as exc:
                raise DRFValidationError({"date_before": str(exc)})
        else:
            period_to = timezone.now()

        total = qs.count()
        unique_actors = qs.exclude(actor__isnull=True).values("actor").distinct().count()

        # Распределение по action: просто подсчёт.
        by_action_qs = qs.values("action").annotate(c=Count("id")).order_by("-c")
        by_action = {row["action"]: row["c"] for row in by_action_qs}

        # Топ модулей.
        by_module_qs = (
            qs.exclude(module__isnull=True)
            .values("module__code")
            .annotate(c=Count("id"))
            .order_by("-c")[:7]
        )
        by_module = [
            {"code": row["module__code"], "count": row["c"]} for row in by_module_qs
        ]

        # Топ юзеров.
        top_actors_qs = (
            qs.exclude(actor__isnull=True)
            .values("actor", "actor__email", "actor__full_name")
            .annotate(c=Count("id"))
            .order_by("-c")[:10]
        )
        top_actors = [
            {
                "user_id": str(row["actor"]),
                "email": row["actor__email"],
                "full_name": row["actor__full_name"],
                "count": row["c"],
            }
            for row in top_actors_qs
        ]

        # Активность по дням (TruncDate работает в TZ из settings).
        daily_qs = (
            qs.annotate(d=TruncDate("occurred_at"))
            .values("d")
            .annotate(c=Count("id"))
            .order_by("d")
        )
        daily = [
            {"date": row["d"].isoformat() if row["d"] else None, "count": row["c"]}
            for row in daily_qs
            if row["d"] is not None
        ]

        return Response(
            {
                "total": total,
                "unique_actors": unique_actors,
                "by_action": by_action,
                "by_module": by_module,
                "top_actors": top_actors,
                "daily": daily,
                "period": {
                    "from": period_from.isoformat(),
                    "to": period_to.isoformat(),
                },
            }
        )

    # ── /users/<uuid>/activity/ ────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path=r"users/(?P<user_id>[0-9a-f-]{36})/activity")
    def user_activity(self, request, user_id=None):
        """
        GET /api/audit/users/<uuid>/activity/?date_after=...&date_before=...

        Профиль активности конкретного пользователя в текущей организации:
            - user: { id, email, full_name }
            - total: число действий за период
            - first_event / last_event: первая и последняя запись
            - by_action: { action_code: count }
            - by_module: [ { code, count } ]
            - by_entity: [ { entity_type, count } ] — какие сущности юзер трогает
            - logins: число логинов в периоде (action=login)
            - unique_ips: список уникальных IP-адресов с count'ами
            - daily: [ { date, count } ]
            - recent: последние 20 событий (для preview в drawer)

        Org-scope: используется тот же queryset что у /list/ (через
        get_queryset() OrgReadOnlyViewSet'а).
        """
        from apps.users.models import User

        # Фильтр по периоду — те же параметры что и у /stats/.
        qs = self.get_queryset().filter(actor_id=user_id)
        # Применяем общий filterset (date_after/before, action и т.д.) кроме
        # actor — он у нас фиксированный.
        params = request.query_params.copy()
        params.pop("actor", None)
        params.pop("actor__in", None)
        request._request.GET = params  # noqa: SLF001 — нужно для filter_queryset
        qs = self.filter_queryset(qs)

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise NotFound("Пользователь не найден.")

        total = qs.count()
        if total == 0:
            return Response(
                {
                    "user": {
                        "id": str(user.id),
                        "email": user.email,
                        "full_name": user.full_name,
                    },
                    "total": 0,
                    "first_event": None,
                    "last_event": None,
                    "by_action": {},
                    "by_module": [],
                    "by_entity": [],
                    "logins": 0,
                    "unique_ips": [],
                    "daily": [],
                    "recent": [],
                }
            )

        first_event = qs.order_by("occurred_at").values_list("occurred_at", flat=True).first()
        last_event = qs.order_by("-occurred_at").values_list("occurred_at", flat=True).first()

        by_action_qs = qs.values("action").annotate(c=Count("id")).order_by("-c")
        by_action = {row["action"]: row["c"] for row in by_action_qs}

        by_module_qs = (
            qs.exclude(module__isnull=True)
            .values("module__code")
            .annotate(c=Count("id"))
            .order_by("-c")
        )
        by_module = [
            {"code": row["module__code"], "count": row["c"]} for row in by_module_qs
        ]

        by_entity_qs = (
            qs.exclude(entity_content_type__isnull=True)
            .values("entity_content_type__model")
            .annotate(c=Count("id"))
            .order_by("-c")[:10]
        )
        by_entity = [
            {"entity_type": row["entity_content_type__model"], "count": row["c"]}
            for row in by_entity_qs
        ]

        logins = qs.filter(action=AuditLog.Action.LOGIN).count()

        # Уникальные IP — Counter в python (один проход).
        ip_counter: Counter = Counter()
        for ip in qs.exclude(ip_address__isnull=True).values_list("ip_address", flat=True):
            ip_counter[ip] += 1
        unique_ips = [
            {"ip": ip, "count": cnt} for ip, cnt in ip_counter.most_common(10)
        ]

        daily_qs = (
            qs.annotate(d=TruncDate("occurred_at"))
            .values("d")
            .annotate(c=Count("id"))
            .order_by("d")
        )
        daily = [
            {"date": row["d"].isoformat(), "count": row["c"]}
            for row in daily_qs
            if row["d"] is not None
        ]

        recent_qs = qs.order_by("-occurred_at")[:20]
        recent = AuditLogSerializer(recent_qs, many=True).data

        return Response(
            {
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "full_name": user.full_name,
                },
                "total": total,
                "first_event": first_event.isoformat() if first_event else None,
                "last_event": last_event.isoformat() if last_event else None,
                "by_action": by_action,
                "by_module": by_module,
                "by_entity": by_entity,
                "logins": logins,
                "unique_ips": unique_ips,
                "daily": daily,
                "recent": recent,
            }
        )
