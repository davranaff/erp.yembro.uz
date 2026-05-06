"""
Хелперы для нормализации «ключевых» полей моделей.

`UpperCodeMixin` — базовый mixin: декларирует список полей в `upper_code_fields`,
и при save() приводит их значения к uppercase. Покрывает 3 точки входа:
    1. DRF API (POST/PATCH) — DRF.save() → model.save()
    2. Django admin / ModelForm — form.save() → model.save()
    3. Прямой ORM .objects.create() / .save()

Не покрывает: `bulk_create` / raw SQL — там нормализация не сработает.
Если нужно — делайте `.upper()` вручную перед bulk-операциями.

Пример:

    class Counterparty(UpperCodeMixin, UUIDModel, TimestampedModel):
        upper_code_fields = ("code",)
        code = models.CharField(...)
"""
from __future__ import annotations


class UpperCodeMixin:
    """Mixin: автоматически приводит поля из upper_code_fields к UPPERCASE при сохранении."""

    upper_code_fields: tuple[str, ...] = ()

    def save(self, *args, **kwargs):
        for field in self.upper_code_fields:
            value = getattr(self, field, None)
            if isinstance(value, str) and value:
                normalized = value.upper()
                if normalized != value:
                    setattr(self, field, normalized)
        super().save(*args, **kwargs)


def normalize_code(value: str | None) -> str | None:
    """Утилита для случаев когда mixin неприменим (bulk-операции, миграции)."""
    if value is None:
        return None
    return value.upper() if isinstance(value, str) else value
