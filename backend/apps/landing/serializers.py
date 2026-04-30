import re

from rest_framework import serializers

from .models import DemoLead


# Базовая разумная регулярка для контакта: либо телефон (с цифрами),
# либо email. Не претендует на полную RFC-совместимость — главное отсечь мусор.
_PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,}$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class DemoLeadSerializer(serializers.ModelSerializer):
    # Honeypot: невидимое поле, заполняется только ботами. Если пришло
    # непустое — тихо отбрасываем заявку (не возвращаем ошибку, чтобы
    # бот не понял что попался). Спам-метрику можно отслеживать через
    # логи / отдельный счётчик при желании.
    website = serializers.CharField(
        required=False, allow_blank=True, write_only=True,
    )

    class Meta:
        model = DemoLead
        fields = ["name", "contact", "company", "website"]
        extra_kwargs = {
            "name": {"max_length": 100, "min_length": 2},
            "contact": {"max_length": 100, "min_length": 5},
            "company": {"max_length": 100, "required": False, "allow_blank": True},
        }

    def validate_contact(self, value: str) -> str:
        v = value.strip()
        if not (_PHONE_RE.match(v) or _EMAIL_RE.match(v)):
            raise serializers.ValidationError(
                "Укажите корректный телефон или email.",
            )
        return v

    def validate_name(self, value: str) -> str:
        v = value.strip()
        # Защита от очевидного мусора (только цифры / только спецсимволы)
        if not re.search(r"[a-zA-Zа-яА-ЯёЁ]", v):
            raise serializers.ValidationError("Укажите имя.")
        return v

    def validate(self, attrs):
        # Тихо игнорируем заявку если honeypot заполнен
        honey = attrs.pop("website", "")
        if honey and honey.strip():
            # Сохраняем "невидимый" маркер чтобы view мог решить пропустить save
            self.context["_honeypot_triggered"] = True
        return attrs
