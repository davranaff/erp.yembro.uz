from django.apps import AppConfig


class TgbotConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tgbot"
    verbose_name = "Telegram Bot"

    def ready(self):
        # Регистрируем signals для авто-рефреша setMyCommands при изменениях
        # RBAC. Импорт внутри ready() — Django гарантирует что AppConfig.ready
        # вызывается ровно один раз после загрузки моделей.
        from . import signals  # noqa: F401
