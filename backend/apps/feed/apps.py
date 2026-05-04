from django.apps import AppConfig


class FeedConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.feed"
    label = "feed"

    def ready(self) -> None:
        # noqa: F401 — импорт ради побочного эффекта подключения receiver'ов
        from . import signals  # noqa: F401
