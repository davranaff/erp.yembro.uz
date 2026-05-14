"""
Grant hr:admin to HEAD_ADMIN role.

Migration 0007 seeded hr permissions for ADMIN and VIEWER but missed
HEAD_ADMIN, leaving that role without access to the HR/payroll module
(time sheets, employees, etc.).
"""
from django.db import migrations


def grant_hr_to_head_admin(apps, schema_editor):
    Module = apps.get_model("modules", "Module")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    Organization = apps.get_model("organizations", "Organization")

    try:
        org = Organization.objects.get(code="DEFAULT")
        hr_module = Module.objects.get(code="hr")
        role = Role.objects.get(organization=org, code="HEAD_ADMIN")
    except (Organization.DoesNotExist, Module.DoesNotExist, Role.DoesNotExist):
        return

    RolePermission.objects.update_or_create(
        role=role,
        module=hr_module,
        defaults={"level": "admin"},
    )


def revoke_hr_from_head_admin(apps, schema_editor):
    Module = apps.get_model("modules", "Module")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    Organization = apps.get_model("organizations", "Organization")

    try:
        org = Organization.objects.get(code="DEFAULT")
        hr_module = Module.objects.get(code="hr")
        role = Role.objects.get(organization=org, code="HEAD_ADMIN")
    except (Organization.DoesNotExist, Module.DoesNotExist, Role.DoesNotExist):
        return

    RolePermission.objects.filter(role=role, module=hr_module).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0011_remove_ledger_from_head_roles"),
        ("modules", "0007_seed_hr_module"),
    ]

    operations = [
        migrations.RunPython(grant_hr_to_head_admin, revoke_hr_from_head_admin),
    ]
