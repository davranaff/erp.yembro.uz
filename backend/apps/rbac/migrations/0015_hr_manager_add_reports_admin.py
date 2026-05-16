"""
Give HR_MANAGER admin-level access to the reports module.

After migration 0009 the role was stripped to hr:admin only.
Analytics (аналитика ЗП, сводки) lives in the reports module —
HR managers need full admin access there too.

Permissions after this migration:
  hr      → admin  (сотрудники, ведомости, графики, компенсации)
  reports → admin  (аналитика)
"""
from django.db import migrations

ROLE_CODE = "HR_MANAGER"
MODULE_CODE = "reports"
LEVEL = "admin"


def grant(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    Module = apps.get_model("modules", "Module")

    try:
        org = Organization.objects.get(code="DEFAULT")
        role = Role.objects.get(organization=org, code=ROLE_CODE)
        module = Module.objects.get(code=MODULE_CODE)
    except (Organization.DoesNotExist, Role.DoesNotExist, Module.DoesNotExist):
        return

    RolePermission.objects.update_or_create(
        role=role,
        module=module,
        defaults={"level": LEVEL},
    )


def revoke(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    Module = apps.get_model("modules", "Module")

    try:
        org = Organization.objects.get(code="DEFAULT")
        role = Role.objects.get(organization=org, code=ROLE_CODE)
        module = Module.objects.get(code=MODULE_CODE)
    except (Organization.DoesNotExist, Role.DoesNotExist, Module.DoesNotExist):
        return

    RolePermission.objects.filter(role=role, module=module).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0014_seed_feed_ingredients_kassas"),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
