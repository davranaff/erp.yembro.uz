"""
Раздать права на новый модуль `sales` существующим системным ролям
ADMIN / VIEWER в организации DEFAULT.
"""
from django.db import migrations


def grant_sales_role_perm(apps, schema_editor):
    Module = apps.get_model("modules", "Module")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    Organization = apps.get_model("organizations", "Organization")

    try:
        org = Organization.objects.get(code="DEFAULT")
        sales_module = Module.objects.get(code="sales")
    except (Organization.DoesNotExist, Module.DoesNotExist):
        return

    for role_code, level in [("ADMIN", "admin"), ("VIEWER", "r")]:
        try:
            role = Role.objects.get(organization=org, code=role_code)
        except Role.DoesNotExist:
            continue
        RolePermission.objects.update_or_create(
            role=role, module=sales_module,
            defaults={"level": level},
        )


def revoke_sales_role_perm(apps, schema_editor):
    Module = apps.get_model("modules", "Module")
    RolePermission = apps.get_model("rbac", "RolePermission")
    try:
        sales_module = Module.objects.get(code="sales")
    except Module.DoesNotExist:
        return
    RolePermission.objects.filter(module=sales_module).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0003_seed_default_org_and_roles"),
        ("modules", "0006_seed_sales_module"),
    ]

    operations = [
        migrations.RunPython(grant_sales_role_perm, revoke_sales_role_perm),
    ]
