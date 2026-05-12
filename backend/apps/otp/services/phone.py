from __future__ import annotations

import re


class PhoneError(ValueError):
    """Невалидный или неподдерживаемый формат номера."""


_DIGITS_RE = re.compile(r"\D+")


def normalize_phone(raw: str) -> str:
    """
    Приводит узбекский номер к формату Eskiz: 12 цифр, начинается с 998.

    Принимает любые написания: '+998 90 123-45-67', '998901234567',
    '901234567'. Возвращает '998901234567'. Поднимает PhoneError, если
    после очистки невозможно собрать корректный номер.
    """
    digits = _DIGITS_RE.sub("", raw or "")
    if not digits:
        raise PhoneError("Пустой номер.")
    if len(digits) == 9:
        digits = f"998{digits}"
    if len(digits) == 12 and digits.startswith("998"):
        return digits
    raise PhoneError("Ожидается номер Узбекистана в формате +998XXXXXXXXX.")
