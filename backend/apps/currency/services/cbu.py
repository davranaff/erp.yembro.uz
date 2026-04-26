"""
Интеграция с ЦБ Узбекистана (cbu.uz).

Источник: https://cbu.uz/ru/arkhiv-kursov-valyut/json/
         https://cbu.uz/ru/arkhiv-kursov-valyut/json/{CODE}/
         https://cbu.uz/ru/arkhiv-kursov-valyut/json/{CODE}/{YYYY-MM-DD}/

Response format (список dict):
    {
      "id": 68,
      "Code": "840",
      "Ccy": "USD",
      "CcyNm_RU": "Доллар США",
      "CcyNm_EN": "US Dollar",
      "Nominal": "1",
      "Rate": "12015.96",
      "Diff": "-26.53",
      "Date": "24.04.2026"
    }
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable, Optional

import requests

CBU_BASE_URL = "https://cbu.uz/ru/arkhiv-kursov-valyut/json"
DEFAULT_TIMEOUT = 15
DEFAULT_SOURCE = "cbu.uz"


class CBUFetchError(Exception):
    """Ошибка при обращении к cbu.uz."""


@dataclass
class CBUSyncResult:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    currencies_created: int = 0

    def as_dict(self) -> dict:
        return {
            "fetched": self.fetched,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "currencies_created": self.currencies_created,
        }


def build_cbu_url(currency_code: Optional[str] = None, on_date: Optional[date] = None) -> str:
    """Собрать URL эндпоинта cbu.uz."""
    parts = [CBU_BASE_URL]
    if currency_code:
        parts.append(currency_code.upper())
    if on_date:
        parts.append(on_date.strftime("%Y-%m-%d"))
    return "/".join(parts) + "/"


def fetch_rates_from_cbu(
    currency_code: Optional[str] = None,
    on_date: Optional[date] = None,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> list[dict]:
    """
    Запросить курсы с cbu.uz.

    Args:
        currency_code: конкретная валюта ("USD"), или None для полного списка.
        on_date: конкретная дата, или None для сегодняшних курсов.

    Returns:
        Список dict в формате CBU.

    Raises:
        CBUFetchError: при HTTP-ошибке, таймауте или невалидном JSON.
    """
    url = build_cbu_url(currency_code, on_date)
    http = session or requests

    try:
        resp = http.get(url, timeout=timeout)
    except requests.RequestException as exc:
        raise CBUFetchError(f"CBU request failed: {exc}") from exc

    if resp.status_code != 200:
        raise CBUFetchError(
            f"CBU returned HTTP {resp.status_code} for {url}: {resp.text[:200]}"
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        raise CBUFetchError(f"CBU returned non-JSON body: {exc}") from exc

    if not isinstance(payload, list):
        raise CBUFetchError(f"CBU returned unexpected shape: {type(payload).__name__}")

    return payload


def _parse_date(raw: str) -> date:
    """CBU дата `DD.MM.YYYY` → `date`."""
    return datetime.strptime(raw, "%d.%m.%Y").date()


def _parse_decimal(raw) -> Decimal:
    return Decimal(str(raw))


def upsert_rates(rows: Iterable[dict], *, source: str = DEFAULT_SOURCE) -> CBUSyncResult:
    """
    Идемпотентный upsert списка курсов в `Currency` + `ExchangeRate`.

    Для каждого row:
      - `Ccy` → ISO-code валюты (создаём Currency если нет).
      - `Date` → DD.MM.YYYY → date.
      - `Nominal`, `Rate` → Decimal.
      - `Code` → numeric_code (840 для USD).

    unique_together ExchangeRate(currency, date, source) гарантирует
    что повторный запуск обновляет, а не дублирует.

    Args:
        rows: iterable of CBU row dicts.
        source: source-label (default "cbu.uz").

    Returns:
        CBUSyncResult со счётчиками.
    """
    from apps.currency.models import Currency, ExchangeRate

    result = CBUSyncResult()
    fetched_at = datetime.now(timezone.utc)

    for row in rows:
        result.fetched += 1
        try:
            code = row["Ccy"]
            rate_val = _parse_decimal(row["Rate"])
            nominal_val = int(row.get("Nominal") or 1)
            rate_date = _parse_date(row["Date"])
            numeric_code = str(row.get("Code") or "")
            name_ru = row.get("CcyNm_RU") or code
            name_en = row.get("CcyNm_EN") or ""
        except (KeyError, ValueError, TypeError):
            result.skipped += 1
            continue

        currency, cur_created = Currency.objects.get_or_create(
            code=code,
            defaults={
                "numeric_code": numeric_code,
                "name_ru": name_ru,
                "name_en": name_en,
                "is_active": True,
            },
        )
        if cur_created:
            result.currencies_created += 1

        _, rate_created = ExchangeRate.objects.update_or_create(
            currency=currency,
            date=rate_date,
            source=source,
            defaults={
                "rate": rate_val,
                "nominal": nominal_val,
                "fetched_at": fetched_at,
            },
        )
        if rate_created:
            result.created += 1
        else:
            result.updated += 1

    return result


def sync_cbu_rates(
    currency_code: Optional[str] = None,
    on_date: Optional[date] = None,
    *,
    source: str = DEFAULT_SOURCE,
) -> CBUSyncResult:
    """
    High-level операция: fetch + upsert. Используется в `tasks.py` и
    в admin action `sync_now`.
    """
    rows = fetch_rates_from_cbu(currency_code=currency_code, on_date=on_date)
    return upsert_rates(rows, source=source)
