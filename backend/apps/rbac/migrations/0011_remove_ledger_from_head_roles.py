"""
Remove ledger:r from module-head roles in all existing organizations.

Affected role codes: HEAD_MATOCHNIK, HEAD_INCUBATION, HEAD_FEEDLOT,
HEAD_SLAUGHTER, HEAD_SUPPLY. Only rows with level='r' are deleted —
if an org admin manually upgraded a role to 'rw' or 'admin', that
intentional change is preserved.
"""
from django.db import migrations


HEAD_ROLE_CODES = {
    "HEAD_MATOCHNIK",
    "HEAD_INCUBATION",
    "HEAD_FEEDLOT",
    "HEAD_SLAUGHTER",
    "HEAD_SUPPLY",
}


def remove_ledger_from_head_roles(apps, schema_editor):
    RolePermission = apps.get_model("rbac", "RolePermission")
    RolePermission.objects.filter(
        role__code__in=HEAD_ROLE_CODES,
        module__code="ledger",
        level="r",
    ).delete()


def restore_ledger_for_head_roles(apps, schema_editor):
    """Reverse: re-add ledger:r to all head roles that currently lack it."""
    RolePermission = apps.get_model("rbac", "RolePermission")
    Role = apps.get_model("rbac", "Role")
    Module = apps.get_model("modules", "Module")

    try:
        ledger_module = Module.objects.get(code="ledger")
    except Module.DoesNotExist:
        return

    for role in Role.objects.filter(code__in=HEAD_ROLE_CODES):
        RolePermission.objects.get_or_create(
            role=role,
            module=ledger_module,
            defaults={"level": "r"},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0010_userscopeassignment_module"),
    ]

    operations = [
        migrations.RunPython(
            remove_ledger_from_head_roles,
            reverse_code=restore_ledger_for_head_roles,
        ),
    ]
