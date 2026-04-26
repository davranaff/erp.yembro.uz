"""
Переиспользуемые serializer-миксины.

В предыдущей версии здесь был FKDisplayMixin, который динамически
добавлял поля-дисплеи через __init__. Он оказался несовместим с DRF
ModelSerializer — DRF резолвит каждое имя из Meta.fields как поле
модели, и наши динамические SerializerMethodField вызывали
ImproperlyConfigured.

Принятое решение: объявлять поля-дисплеи явно в каждом сериализаторе
через serializers.CharField(source="fk.attr", read_only=True) или
SerializerMethodField. См. apps.nomenclature.serializers.
"""
from __future__ import annotations


class OrganizationContextSerializerMixin:
    """Хелпер для извлечения request.organization из context."""

    def _get_organization(self):
        request = self.context.get("request")
        return getattr(request, "organization", None) if request else None
