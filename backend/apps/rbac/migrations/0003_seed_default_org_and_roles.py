from decimal import Decimal

from django.db import migrations
from django.utils import timezone


def seed_default_org(apps, schema_editor):
    Currency = apps.get_model("currency", "Currency")
    Organization = apps.get_model("organizations", "Organization")
    Module = apps.get_model("modules", "Module")
    OrganizationModule = apps.get_model("modules", "OrganizationModule")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")

    uzs, _ = Currency.objects.get_or_create(
        code="UZS",
        defaults={
            "numeric_code": "860",
            "name_ru": "Узбекский сум",
            "name_en": "Uzbekistan Som",
            "is_active": True,
        },
    )

    org, _ = Organization.objects.get_or_create(
        code="DEFAULT",
        defaults={
            "name": "Default",
            "direction": "broiler",
            "accounting_currency": uzs,
            "timezone": "Asia/Tashkent",
            "is_active": True,
        },
    )

    now = timezone.now()
    for module in Module.objects.all():
        OrganizationModule.objects.get_or_create(
            organization=org,
            module=module,
            defaults={"is_enabled": True, "enabled_at": now},
        )

    admin_role, _ = Role.objects.get_or_create(
        organization=org,
        code="ADMIN",
        defaults={
            "name": "Администратор",
            "description": "Полный доступ ко всем модулям.",
            "is_system": True,
            "is_active": True,
        },
    )
    viewer_role, _ = Role.objects.get_or_create(
        organization=org,
        code="VIEWER",
        defaults={
            "name": "Наблюдатель",
            "description": "Только просмотр.",
            "is_system": True,
            "is_active": True,
        },
    )

    for module in Module.objects.all():
        RolePermission.objects.update_or_create(
            role=admin_role,
            module=module,
            defaults={"level": "admin"},
        )
        RolePermission.objects.update_or_create(
            role=viewer_role,
            module=module,
            defaults={"level": "r"},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0002_initial"),
        ("modules", "0003_seed_modules"),
        ("organizations", "0002_initial"),
        ("currency", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_default_org, migrations.RunPython.noop),
    ]
