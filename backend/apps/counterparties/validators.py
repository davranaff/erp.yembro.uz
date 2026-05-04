from django.core.exceptions import ValidationError


def validate_inn(value: str) -> None:
    if not value:
        return
    if not value.isdigit() or len(value) not in (9, 14):
        raise ValidationError("ИНН должен содержать 9 или 14 цифр.")
