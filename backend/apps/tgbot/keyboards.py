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
    """Одиночная кнопка «← Orqaga»."""
    return kb([("← Orqaga", home_callback)], cols=1)


def kb_back_home(back_callback: str = "home") -> dict:
    """Двойная кнопка: «← Orqaga» (back_callback) + «🏠 Bosh» (home).

    Применяется в drill-down экранах где «назад» != «домой» (например в
    карточке заказа: назад → список заказов, домой → главное меню).
    Если `back_callback == "home"` — фактически дубль, в этом случае
    лучше использовать `kb_back("home")`.
    """
    return kb([
        ("← Orqaga", back_callback),
        ("🏠 Bosh", "home"),
    ], cols=2)


def kb_periods(prefix: str, current: str | None = None) -> dict:
    """Клавиатура переключения периодов: today / week / month (узбекский).

    `prefix` — namespace callback_data (напр. `fin:pnl`). Нажатая кнопка
    пометится • если совпадает с `current`.
    """
    options = [("today", "Bugun"), ("week", "Hafta"), ("month", "Oy")]
    return kb(
        [
            (f"• {label}" if k == current else label, f"{prefix}:{k}")
            for k, label in options
        ],
        cols=3,
    )


# ─── Pagination ──────────────────────────────────────────────────────────


PAGE_SIZE = 10


def kb_pagination(
    prefix: str,
    page: int,
    total: int,
    *,
    back_to: str | None = None,
    page_size: int = PAGE_SIZE,
) -> dict:
    """Универсальная пагинация-клавиатура.

    Кнопки: «← Oldingi» (если page>1) · «N/Total» (noop) · «Keyingi →»
    (если page<pages). Если `back_to` задан — добавляется ряд с
    «← Orqaga» / «🏠 Bosh».

    callback_data: `{prefix}:{N}` для смены страницы. Центральная плашка
    шлёт `noop` — handler возвращает None (см. handlers/finance.handle_noop).

    Пример:
        kb_pagination("fin:debt", page=2, total=27, back_to="home:fin")
    """
    pages = max(1, (total + page_size - 1) // page_size)
    nav: list[tuple[str, str]] = []
    if page > 1:
        nav.append(("← Oldingi", f"{prefix}:{page - 1}"))
    nav.append((f"{page}/{pages}", "noop"))
    if page < pages:
        nav.append(("Keyingi →", f"{prefix}:{page + 1}"))

    rows = [nav]
    if back_to:
        rows.append([("← Orqaga", back_to), ("🏠 Bosh", "home")])
    return {"inline_keyboard": [
        [{"text": t, "callback_data": _validate(cb)} for t, cb in row]
        for row in rows
    ]}


def parse_page(args: list[str], default: int = 1) -> int:
    """Извлекает номер страницы из callback args."""
    if not args:
        return default
    try:
        n = int(args[0])
        return max(1, n)
    except (ValueError, TypeError):
        return default


# ─── Reply keyboard (постоянная клавиатура внизу) ─────────────────────────


def reply_kb(rows: list[list[str]], *, persistent: bool = True) -> dict:
    """ReplyKeyboardMarkup — нижняя постоянная клавиатура.

    Тапы по кнопкам шлют их текст как обычное сообщение — handler ловит
    через @command или текстовое сравнение. Используется для клиент-кабинета:
    юзеры мобайла предпочитают видеть постоянные кнопки внизу, а не
    inline под отдельным сообщением (которое скроллится вверх).

    Args:
        rows: матрица строк (каждая внутренняя — ряд кнопок).
        persistent: ``is_persistent=True`` чтобы клавиатура не схлопывалась.
                    Telegram также любит ``resize_keyboard=True`` для
                    компактной высоты.
    """
    return {
        "keyboard": [[{"text": label} for label in row] for row in rows],
        "resize_keyboard": True,
        "is_persistent": persistent,
    }


def reply_kb_remove() -> dict:
    """Удалить ReplyKeyboardMarkup (вернуть стандартную клавиатуру)."""
    return {"remove_keyboard": True}
