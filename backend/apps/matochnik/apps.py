from django.apps import AppConfig


class MatochnikConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.matochnik"
    label = "matochnik"

    def ready(self):
        # Регистрируем post_save сигнал BreedingMortality → current_heads--
        from . import signals  # noqa: F401
