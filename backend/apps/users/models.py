from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel

from .managers import UserManager


class User(UUIDModel, TimestampedModel, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email


class UserFavoritePage(UUIDModel, TimestampedModel):
    """
    Закреплённые пользователем страницы навигации.

    Хранится per-user, без привязки к организации — закладки следуют за
    пользователем при переключении организаций. Используется в Sidebar
    (секция «Закреплённые» сверху) и в FavoritesMenu (дропдаун в топбаре).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_pages",
    )
    href = models.CharField(
        max_length=255,
        help_text="Внутренний путь страницы, например '/sales' или '/finance/cashbox'.",
    )
    label = models.CharField(
        max_length=128,
        help_text="Snapshot человекочитаемого названия страницы из nav.ts.",
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Для будущей drag-reorder. Сейчас всегда 0, ordering MRU.",
    )

    class Meta:
        unique_together = (("user", "href"),)
        ordering = ["sort_order", "-created_at"]
        indexes = [
            models.Index(fields=["user", "sort_order"]),
        ]
        verbose_name = "Закреплённая страница"
        verbose_name_plural = "Закреплённые страницы"

    def __str__(self):
        return f"{self.user.email} · {self.label}"

    def clean(self):
        super().clean()
        if self.href and not self.href.startswith("/"):
            raise ValidationError({"href": "Путь должен начинаться со слеша."})
