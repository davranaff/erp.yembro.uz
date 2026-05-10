"""
Резолюшен языка для public API каталога.

Порядок: ?lang= → Accept-Language → дефолт "ru". Сериализаторы используют
полученный код для выбора суффиксированного поля (`name_uz`/`name_en`).
"""
from __future__ import annotations

from typing import Final

LANGS: Final[tuple[str, ...]] = ("ru", "uz", "en")
DEFAULT_LANG: Final[str] = "ru"


def resolve_lang(request) -> str:
    """Вернёт код языка из {ru, uz, en}. Никогда не падает."""
    raw = request.query_params.get("lang") if hasattr(request, "query_params") else None
    if raw and raw in LANGS:
        return raw

    accept = request.META.get("HTTP_ACCEPT_LANGUAGE", "") if hasattr(request, "META") else ""
    if accept:
        # Берём первый кусок до запятой/точки с запятой и режем регион (uz-UZ → uz).
        primary = accept.split(",", 1)[0].split(";", 1)[0].strip().lower()
        primary = primary.split("-", 1)[0]
        if primary in LANGS:
            return primary

    return DEFAULT_LANG


def localized(obj, field: str, lang: str) -> str:
    """Достаёт `field_<lang>`, fallback на `field_ru`, fallback на пустую строку."""
    val = getattr(obj, f"{field}_{lang}", None)
    if val:
        return val
    fallback = getattr(obj, f"{field}_{DEFAULT_LANG}", None)
    return fallback or ""
