from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class AccessLevel(models.TextChoices):
    NONE = "none", "Нет доступа"
    READ = "r", "Просмотр"
    READ_WRITE = "rw", "Ввод документов"
    ADMIN = "admin", "Администратор модуля"


class Role(UUIDModel, TimestampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="roles",
    )
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = (("organization", "code"),)
        ordering = ["organization__code", "code"]
        verbose_name = "Роль"
        verbose_name_plural = "Роли"

    def __str__(self):
        return f"{self.organization.code} · {self.name}"


class RolePermission(UUIDModel, TimestampedModel):
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="permissions",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )
    level = models.CharField(
        max_length=8,
        choices=AccessLevel.choices,
        default=AccessLevel.NONE,
    )

    class Meta:
        unique_together = (("role", "module"),)
        verbose_name = "Право роли"
        verbose_name_plural = "Права ролей"

    def __str__(self):
        return f"{self.role.name} · {self.module.code} · {self.get_level_display()}"


class UserRole(UUIDModel, TimestampedModel):
    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="user_roles",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("membership", "role"),)
        verbose_name = "Назначение роли"
        verbose_name_plural = "Назначения ролей"

    def __str__(self):
        return f"{self.membership} · {self.role.name}"

    def clean(self):
        super().clean()
        if self.membership_id and self.role_id:
            if self.membership.organization_id != self.role.organization_id:
                raise ValidationError(
                    "Роль и участие должны принадлежать одной организации."
                )


class UserModuleAccessOverride(UUIDModel, TimestampedModel):
    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="module_overrides",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.CASCADE,
        related_name="+",
    )
    level = models.CharField(max_length=8, choices=AccessLevel.choices)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = (("membership", "module"),)
        verbose_name = "Индивидуальный доступ к модулю"
        verbose_name_plural = "Индивидуальные доступы к модулям"

    def __str__(self):
        return f"{self.membership} · {self.module.code} · {self.get_level_display()}"
