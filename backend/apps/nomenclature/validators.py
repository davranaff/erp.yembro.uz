"""
Защитная валидация привязки `NomenclatureItem` к нужному модулю.

Используется в `clean()` моделей (RecipeComponent, RawMaterialBatch, Batch,
SlaughterYield...), где FK на NomenclatureItem семантически ограничен
конкретным модулем. UI обычно даёт оператору только подходящий список
(через `?module_code=` фильтр), но через API/админку/импорт можно
проскочить — здесь подстраховка.

Логика:
  - если у item.category нет module → пропускаем (общая категория, разрешено)
  - если есть и совпадает с `expected_module_code` → ОК
  - иначе → ValidationError на конкретное поле

`field_name` — имя поля в форме / модели для красивого сообщения
("nomenclature", "egg_nomenclature" и т.п.).
"""
from __future__ import annotations

from django.core.exceptions import ValidationError


def validate_nomenclature_module(
    item,
    expected_module_code: str,
    *,
    field_name: str = "nomenclature",
) -> None:
    """Бросает ValidationError если category.module указан и не совпадает.

    Принимает уже-загруженный `NomenclatureItem` (не id). Категория должна
    быть подгружена (или дёрнется один доп. SELECT — ок, валидация редкая).
    """
    if item is None:
        return
    category = getattr(item, "category", None)
    if category is None:
        return
    module = getattr(category, "module", None)
    if module is None:
        # «общая» категория — разрешена везде
        return
    if module.code != expected_module_code:
        raise ValidationError({
            field_name: (
                f"Номенклатура «{item.sku}» относится к модулю "
                f"«{module.code}», а не «{expected_module_code}». "
                f"Выберите подходящую позицию."
            ),
        })
