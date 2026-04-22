from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.config import get_settings

TEMPLATE_DEBT_REMINDER = "debt_reminder"
TEMPLATE_PRODUCT_ALERT = "product_alert"
TEMPLATE_GENERAL = "general_notice"
SUPPORTED_TEMPLATE_KEYS = (
    TEMPLATE_DEBT_REMINDER,
    TEMPLATE_PRODUCT_ALERT,
    TEMPLATE_GENERAL,
)


@dataclass(slots=True)
class TelegramSendResult:
    ok: bool
    error: str | None = None
    provider_message_id: str | None = None


class TelegramNotificationGateway:
    def __init__(self) -> None:
        settings = get_settings()
        self._bot_token = str(settings.telegram_bot_token or "").strip()
        self._base_url = str(settings.telegram_api_base_url or "https://api.telegram.org").strip().rstrip("/")
        self._parse_mode = str(settings.telegram_parse_mode or "").strip() or None

    @property
    def is_configured(self) -> bool:
        return bool(self._bot_token)

    async def send_message(
        self,
        *,
        chat_id: str,
        text: str,
    ) -> TelegramSendResult:
        if not self.is_configured:
            return TelegramSendResult(ok=False, error="Telegram bot token is not configured")

        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if self._parse_mode:
            payload["parse_mode"] = self._parse_mode

        endpoint = f"{self._base_url}/bot{self._bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(endpoint, json=payload)
        except Exception as exc:
            return TelegramSendResult(ok=False, error=f"Telegram request failed: {exc}")

        if response.status_code >= 400:
            return TelegramSendResult(
                ok=False,
                error=f"Telegram API error: HTTP {response.status_code}",
            )

        try:
            body = response.json()
        except Exception:
            return TelegramSendResult(ok=False, error="Telegram API returned invalid JSON")

        if not isinstance(body, dict):
            return TelegramSendResult(ok=False, error="Telegram API returned invalid response body")

        if not bool(body.get("ok")):
            description = str(body.get("description") or "Unknown Telegram error")
            return TelegramSendResult(ok=False, error=description)

        provider_message_id = None
        result_body = body.get("result")
        if isinstance(result_body, dict) and result_body.get("message_id") is not None:
            provider_message_id = str(result_body.get("message_id"))

        return TelegramSendResult(ok=True, provider_message_id=provider_message_id)


def _to_decimal(value: object | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _format_money(value: object | None) -> str:
    decimal_value = _to_decimal(value)
    quantized = decimal_value.quantize(Decimal("0.01"))
    return f"{quantized:,.2f}".replace(",", " ")


def _normalize_name(client: dict[str, Any]) -> str:
    company_name = str(client.get("company_name") or "").strip()
    if company_name:
        return company_name

    first_name = str(client.get("first_name") or "").strip()
    last_name = str(client.get("last_name") or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        return full_name

    return str(client.get("id") or "")


def _format_purchase_line(purchase: dict[str, Any] | None) -> str:
    if purchase is None:
        return "последние покупки не найдены"

    date_value = str(purchase.get("purchased_on") or "").strip() or "дата не указана"
    item_name = str(purchase.get("item_name") or "товар").strip()
    quantity = str(purchase.get("quantity") or "0").strip()
    unit = str(purchase.get("unit") or "шт").strip()
    amount = _format_money(purchase.get("amount"))
    currency = str(purchase.get("currency") or "").strip()
    amount_part = f", сумма {amount} {currency}".rstrip()
    return f"{date_value}: {item_name}, {quantity} {unit}{amount_part}"


def build_notification_templates(
    *,
    client: dict[str, Any],
    debt_summary: dict[str, Any],
    recent_purchases: list[dict[str, Any]],
) -> list[dict[str, str]]:
    client_name = _normalize_name(client)
    open_count = int(debt_summary.get("open_count") or 0)
    outstanding_amount = _format_money(debt_summary.get("outstanding_amount"))
    primary_currency = str(debt_summary.get("currency") or "").strip() or "UZS"
    latest_purchase = _format_purchase_line(recent_purchases[0] if recent_purchases else None)

    debt_message = (
        f"Assalomu alaykum, {client_name}.\n"
        f"Eslatib o'tamiz: sizda {open_count} ta ochiq qarzdorlik bor.\n"
        f"Joriy qoldiq: {outstanding_amount} {primary_currency}.\n"
        f"Oxirgi xarid: {latest_purchase}.\n"
        "To'lov muddatini aniqlashtirish uchun biz bilan bog'laning."
    )

    product_message = (
        f"Assalomu alaykum, {client_name}.\n"
        "Siz uchun bo'limdagi yangi takliflar tayyor.\n"
        f"Oxirgi xaridingiz: {latest_purchase}.\n"
        "Agar yangi partiya kerak bo'lsa, shu xabarga javob yozing."
    )

    general_message = (
        f"Assalomu alaykum, {client_name}.\n"
        "Bu sizning shaxsiy xabaringiz.\n"
        f"Ma'lumot uchun: {latest_purchase}."
    )

    return [
        {
            "key": TEMPLATE_DEBT_REMINDER,
            "title": "Qarz eslatmasi",
            "description": "Qarz summasi va oxirgi xarid bilan eslatma.",
            "message": debt_message,
        },
        {
            "key": TEMPLATE_PRODUCT_ALERT,
            "title": "Tovar bo'yicha ogohlantirish",
            "description": "Oxirgi xarid asosidagi taklif xabari.",
            "message": product_message,
        },
        {
            "key": TEMPLATE_GENERAL,
            "title": "Umumiy xabar",
            "description": "Mijozga individual erkin matn xabari.",
            "message": general_message,
        },
    ]


def resolve_template_message(
    *,
    template_key: str,
    templates: list[dict[str, str]],
    custom_message: str | None,
) -> str:
    custom_candidate = str(custom_message or "").strip()
    if custom_candidate:
        return custom_candidate

    normalized_key = str(template_key or "").strip().lower()
    for template in templates:
        if str(template.get("key") or "").strip().lower() == normalized_key:
            return str(template.get("message") or "").strip()

    return ""


async def fetch_client_notification_context(
    *,
    db,
    actor_organization_id: str,
    client_id: str,
    department_id: str | None,
    recent_limit: int = 5,
) -> dict[str, Any] | None:
    client_row = await db.fetchrow(
        """
        SELECT id, organization_id, first_name, last_name, company_name, phone, email, telegram_chat_id
        FROM clients
        WHERE id = $1
          AND organization_id = $2
        LIMIT 1
        """,
        client_id,
        actor_organization_id,
    )
    if client_row is None:
        return None
    client = dict(client_row)

    department_clause = ""
    params: list[object] = [actor_organization_id, client_id]
    if department_id:
        params.append(department_id)
        department_clause = f" AND department_id = ${len(params)}"

    debt_summary_row = await db.fetchrow(
        f"""
        SELECT
            COALESCE(SUM(CASE WHEN cd.status IN ('open', 'partially_paid') AND cd.is_active = true THEN 1 ELSE 0 END), 0) AS open_count,
            COALESCE(SUM(CASE WHEN cd.status IN ('open', 'partially_paid') AND cd.is_active = true THEN cd.amount_total ELSE 0 END), 0) AS total_amount,
            COALESCE(SUM(CASE WHEN cd.status IN ('open', 'partially_paid') AND cd.is_active = true THEN cd.amount_paid ELSE 0 END), 0) AS paid_amount,
            COALESCE(MAX(cur.code), 'UZS') AS currency
        FROM client_debts AS cd
        LEFT JOIN currencies AS cur ON cur.id = cd.currency_id
        WHERE cd.organization_id = $1
          AND cd.client_id = $2
          {department_clause}
        """,
        *params,
    )
    debt_summary_raw = dict(debt_summary_row) if debt_summary_row is not None else {}
    total_amount = _to_decimal(debt_summary_raw.get("total_amount"))
    paid_amount = _to_decimal(debt_summary_raw.get("paid_amount"))
    debt_summary = {
        "open_count": int(debt_summary_raw.get("open_count") or 0),
        "total_amount": str(total_amount),
        "paid_amount": str(paid_amount),
        "outstanding_amount": str((total_amount - paid_amount).quantize(Decimal("0.01"))),
        "currency": debt_summary_raw.get("currency") or "UZS",
    }

    debt_params = list(params)
    debt_params.append(max(1, recent_limit))
    recent_debts_rows = await db.fetch(
        f"""
        SELECT
            cd.id, cd.item_type, cd.item_key, cd.quantity, cd.unit,
            cd.amount_total, cd.amount_paid, cur.code AS currency,
            cd.issued_on, cd.due_on, cd.status
        FROM client_debts AS cd
        LEFT JOIN currencies AS cur ON cur.id = cd.currency_id
        WHERE cd.organization_id = $1
          AND cd.client_id = $2
          {department_clause.replace('department_id', 'cd.department_id')}
          AND cd.is_active = true
        ORDER BY COALESCE(cd.due_on, cd.issued_on) ASC, cd.created_at DESC
        LIMIT ${len(debt_params)}
        """,
        *debt_params,
    )
    recent_debts = [dict(row) for row in recent_debts_rows]

    purchase_params: list[object] = [actor_organization_id, client_id]
    purchase_department_clause_egg = ""
    purchase_department_clause_feed = ""
    purchase_department_clause_chick = ""
    purchase_department_clause_slaughter = ""
    if department_id:
        purchase_params.append(department_id)
        department_param_index = len(purchase_params)
        purchase_department_clause_egg = f" AND es.department_id = ${department_param_index}"
        purchase_department_clause_feed = f" AND fps.department_id = ${department_param_index}"
        purchase_department_clause_chick = f" AND cs.department_id = ${department_param_index}"
        purchase_department_clause_slaughter = f" AND ss.department_id = ${department_param_index}"
    purchase_params.append(max(1, recent_limit))

    recent_purchase_rows = await db.fetch(
        f"""
        SELECT *
        FROM (
            SELECT
                es.shipped_on AS purchased_on,
                'egg' AS source_module,
                COALESCE(NULLIF(TRIM(ep.note), ''), 'Egg shipment') AS item_name,
                es.eggs_count AS quantity,
                es.unit AS unit,
                (COALESCE(es.unit_price, 0) * COALESCE(es.eggs_count, 0)) AS amount,
                cur_es.code AS currency,
                es.invoice_no AS reference_no
            FROM egg_shipments AS es
            LEFT JOIN egg_production AS ep ON ep.id = es.production_id
            LEFT JOIN currencies AS cur_es ON cur_es.id = es.currency_id
            WHERE es.organization_id = $1
              AND es.client_id = $2
              {purchase_department_clause_egg}

            UNION ALL

            SELECT
                fps.shipped_on AS purchased_on,
                'feed' AS source_module,
                COALESCE(ft.name, ft.code, 'Feed product') AS item_name,
                fps.quantity AS quantity,
                fps.unit AS unit,
                (COALESCE(fps.unit_price, 0) * COALESCE(fps.quantity, 0)) AS amount,
                cur_fps.code AS currency,
                fps.invoice_no AS reference_no
            FROM feed_product_shipments AS fps
            LEFT JOIN feed_types AS ft ON ft.id = fps.feed_type_id
            LEFT JOIN currencies AS cur_fps ON cur_fps.id = fps.currency_id
            WHERE fps.organization_id = $1
              AND fps.client_id = $2
              {purchase_department_clause_feed}

            UNION ALL

            SELECT
                cs.shipped_on AS purchased_on,
                'incubation' AS source_module,
                COALESCE(ib.batch_code, 'Chick shipment') AS item_name,
                cs.chicks_count AS quantity,
                'pcs' AS unit,
                (COALESCE(cs.unit_price, 0) * COALESCE(cs.chicks_count, 0)) AS amount,
                cur_cs.code AS currency,
                cs.invoice_no AS reference_no
            FROM chick_shipments AS cs
            LEFT JOIN incubation_runs AS ir ON ir.id = cs.run_id
            LEFT JOIN incubation_batches AS ib ON ib.id = ir.batch_id
            LEFT JOIN currencies AS cur_cs ON cur_cs.id = cs.currency_id
            WHERE cs.organization_id = $1
              AND cs.client_id = $2
              {purchase_department_clause_chick}

            UNION ALL

            SELECT
                ss.shipped_on AS purchased_on,
                'slaughter' AS source_module,
                COALESCE(sp.part_name, sp.code, 'Semi product') AS item_name,
                ss.quantity AS quantity,
                ss.unit AS unit,
                (COALESCE(ss.unit_price, 0) * COALESCE(ss.quantity, 0)) AS amount,
                cur_ss.code AS currency,
                ss.invoice_no AS reference_no
            FROM slaughter_semi_product_shipments AS ss
            LEFT JOIN slaughter_semi_products AS sp ON sp.id = ss.semi_product_id
            LEFT JOIN currencies AS cur_ss ON cur_ss.id = ss.currency_id
            WHERE ss.organization_id = $1
              AND ss.client_id = $2
              {purchase_department_clause_slaughter}
        ) AS purchases
        ORDER BY purchased_on DESC
        LIMIT ${len(purchase_params)}
        """,
        *purchase_params,
    )
    recent_purchases = [dict(row) for row in recent_purchase_rows]

    templates = build_notification_templates(
        client=client,
        debt_summary=debt_summary,
        recent_purchases=recent_purchases,
    )

    return {
        "client": {
            "id": str(client["id"]),
            "name": _normalize_name(client),
            "phone": client.get("phone"),
            "email": client.get("email"),
            "telegram_chat_id": client.get("telegram_chat_id"),
        },
        "debt_summary": debt_summary,
        "recent_debts": recent_debts,
        "recent_purchases": recent_purchases,
        "templates": templates,
    }


__all__ = [
    "SUPPORTED_TEMPLATE_KEYS",
    "TelegramNotificationGateway",
    "build_notification_templates",
    "fetch_client_notification_context",
    "resolve_template_message",
]
