import re

from rest_framework import serializers


_PURPOSE_RE = re.compile(r"^[a-z0-9_\-]{1,32}$")


class OtpRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    purpose = serializers.CharField(max_length=32)
    # Опциональный шаблон от клиента — но мы его принимаем только если
    # настройка явно разрешает (см. views). По умолчанию игнорируется.
    message_template = serializers.CharField(
        max_length=200, required=False, allow_blank=False,
    )

    def validate_purpose(self, value: str) -> str:
        value = (value or "").strip().lower()
        if not _PURPOSE_RE.match(value):
            raise serializers.ValidationError(
                "purpose: разрешены только латиница в нижнем регистре, "
                "цифры, '_' и '-', до 32 символов."
            )
        return value


class OtpVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    purpose = serializers.CharField(max_length=32)
    code = serializers.CharField(min_length=4, max_length=8)

    def validate_purpose(self, value: str) -> str:
        value = (value or "").strip().lower()
        if not _PURPOSE_RE.match(value):
            raise serializers.ValidationError("purpose: некорректный формат.")
        return value

    def validate_code(self, value: str) -> str:
        value = (value or "").strip()
        if not value.isdigit():
            raise serializers.ValidationError("Код должен состоять из цифр.")
        return value
