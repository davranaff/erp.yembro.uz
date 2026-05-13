"""
Генерация уникальных EAN-13 штрих-кодов для моделей с
`unique_together = ('organization', 'barcode')`.

EAN-13: 12 значащих цифр + 1 контрольная.
Контрольная: 10 − ((d1 + d3 + d5 + d7 + d9 + d11)
                 + 3·(d2 + d4 + d6 + d8 + d10 + d12)) mod 10, затем mod 10.
"""
from __future__ import annotations

import secrets


def _ean13_checksum(d12: str) -> int:
    s = 0
    for i, c in enumerate(d12):
        n = int(c)
        s += n if i % 2 == 0 else n * 3
    return (10 - s % 10) % 10


def generate_ean13_barcode(model_cls, organization, *, prefix: str = "", retries: int = 5) -> str:
    """Сгенерировать уникальный (в рамках organization) EAN-13.

    prefix — опциональные ведущие цифры для тематической группировки
    (например "210" для VetDrug, "240" для FeedBagLot). Не-цифры
    отбрасываются, длина обрезается до 12.
    """
    pref = "".join(c for c in prefix if c.isdigit())[:12]
    rand_len = 12 - len(pref)
    for _ in range(retries):
        rand_part = "".join(str(secrets.randbelow(10)) for _ in range(rand_len))
        d12 = pref + rand_part
        candidate = d12 + str(_ean13_checksum(d12))
        if not model_cls.objects.filter(
            organization=organization, barcode=candidate
        ).exists():
            return candidate
    raise RuntimeError(
        f"Не удалось сгенерировать уникальный EAN-13 для "
        f"{model_cls.__name__} после {retries} попыток."
    )
