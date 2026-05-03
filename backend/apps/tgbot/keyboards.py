"""
Helpers для построения InlineKeyboardMarkup payload-ов Telegram.

Telegram ограничивает callback_data 64 байтами в utf-8. Для длинных payload-ов
(uuid партии = 36 chars) обычно используют короткие префиксы + отдельный
look-up. У нас ID партии не передаём в callback — вместо этого внутри
обработчика дёргаем БД по doc_number / latest active. Так что для inline-кнопок
достаточно компактных префиксов вроде `home:fin`, `fin:pnl:week`,
`org:set:<uuid>`.
"""
from __future__ import annotations

from typing import Iterable


_MAX_BYTES = 64


def _validate(callback_data: str) -> str:
    encoded = callback_data.encode("utf-8")
    if len(encoded) > _MAX_BYTES:
        raise ValueError(
            f"callback_data слишком длинная ({len(encoded)} байт): "
            f"{callback_data!r}. Максимум {_MAX_BYTES} bytes."
        )
    return callback_data


def kb(buttons: Iterable[tuple[str, str]], cols: int = 2) -> dict:
    """Сборка InlineKeyboardMarkup из плоского списка `(label, callback_data)`.

    Раскладка строк по `cols` колонкам. Пустой список → пустая клавиатура
    (Telegram примет, кнопок не будет).

    Пример:
        kb([("💰 Финансы", "home:fin"), ("📦 Партии", "home:batch")], cols=2)
    """
    rows: list[list[dict]] = []
    row: list[dict] = []
    for label, data in buttons:
        row.append({"text": label, "callback_data": _validate(data)})
        if len(row) >= cols:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return {"inline_keyboard": rows}


def kb_back(home_callback: str = "home") -> dict:
    """Одиночная кнопка «Назад» — возвращает к главному меню."""
    return kb([("← Назад", home_callback)], cols=1)


def kb_periods(prefix: str, current: str | None = None) -> dict:
    """Стандартная клавиатура переключения периодов: today / week / month.

    `prefix` — namespace callback_data (напр. `fin:pnl`). Нажатая кнопка
    пометится • если совпадает с `current`.
    """
    options = [("today", "Сегодня"), ("week", "Неделя"), ("month", "Месяц")]
    return kb(
        [
            (f"• {label}" if k == current else label, f"{prefix}:{k}")
            for k, label in options
        ],
        cols=3,
    )
