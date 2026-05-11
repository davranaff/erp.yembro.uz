"""
Раздать права на новый модуль `hr` существующим системным ролям
ADMIN / VIEWER в организации DEFAULT (паттерн как для sales в 0004).
"""
from django.db import migrations


def grant_hr_role_perm(apps, schema_editor):
    Module = apps.get_model("modules", "Module")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    Organization = apps.get_model("organizations", "Organization")

    try:
        org = Organization.objects.get(code="DEFAULT")
        hr_module = Module.objects.get(code="hr")
    except (Organization.DoesNotExist, Module.DoesNotExist):
        return

    for role_code, level in [("ADMIN", "admin"), ("VIEWER", "r")]:
        try:
            role = Role.objects.get(organization=org, code=role_code)
        except Role.DoesNotExist:
            continue
        RolePermission.objects.update_or_create(
            role=role, module=hr_module,
            defaults={"level": level},
        )


def revoke_hr_role_perm(apps, schema_editor):
    Module = apps.get_model("modules", "Module")
    RolePermission = apps.get_model("rbac", "RolePermission")
    try:
        hr_module = Module.objects.get(code="hr")
    except Module.DoesNotExist:
        return
    RolePermission.objects.filter(module=hr_module).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0006_user_scope_assignment"),
        ("modules", "0007_seed_hr_module"),
    ]

    operations = [
        migrations.RunPython(grant_hr_role_perm, revoke_hr_role_perm),
    ]
