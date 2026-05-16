"""
Grant sales:r to HEAD_MATOCHNIK, HEAD_INCUBATION, HEAD_FEEDLOT, HEAD_SUPPLY.

These roles had sales=none (hidden in sidebar). All production heads
should be able to see the sales module (read-only).

HEAD_SLAUGHTER already has sales:rw, HEAD_ADMIN/ACCOUNTING/SALES have admin.
"""
from django.db import migrations

ROLES_TO_GRANT = [
    "HEAD_MATOCHNIK",
    "HEAD_INCUBATION",
    "HEAD_FEEDLOT",
    "HEAD_SUPPLY",
]


def grant(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    Module = apps.get_model("modules", "Module")

    try:
        org = Organization.objects.get(code="DEFAULT")
        sales = Module.objects.get(code="sales")
    except (Organization.DoesNotExist, Module.DoesNotExist):
        return

    for code in ROLES_TO_GRANT:
        try:
            role = Role.objects.get(organization=org, code=code)
        except Role.DoesNotExist:
            continue
        RolePermission.objects.update_or_create(
            role=role,
            module=sales,
            defaults={"level": "r"},
        )


def revoke(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    Module = apps.get_model("modules", "Module")

    try:
        org = Organization.objects.get(code="DEFAULT")
        sales = Module.objects.get(code="sales")
    except (Organization.DoesNotExist, Module.DoesNotExist):
        return

    RolePermission.objects.filter(
        role__organization=org,
        role__code__in=ROLES_TO_GRANT,
        module=sales,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0015_hr_manager_add_reports_admin"),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
