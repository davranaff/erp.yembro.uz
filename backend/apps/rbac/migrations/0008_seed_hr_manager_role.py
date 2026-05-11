"""
Cеяная роль HR_MANAGER — кадровик-зарплатчик.

Управляет:
  • сотрудниками (Person, Membership) в модуле hr
  • табелями, графиками, отпусками, праздниками
  • компенсационными планами и их историей
  • начислениями (ведомостями), снапшотами, корректировками
  • расчётом ЗП за период (PayrollRun)

Уровни доступа:
  • hr        → admin (полный контроль)
  • core      → r     (организации, базовые справочники)
  • reports   → r     (отчёты — для аналитики)
  • ledger    → r     (просмотр проводок по выплатам ЗП)

К производственным модулям (matochnik / incubation / feedlot / slaughter /
feed / vet / stock / purchases / sales) и к «admin» HR-менеджер доступа
не получает — это специально, кадровик не должен лезть в операционку.

Накатывается в организации DEFAULT (паттерн как у sales/hr миграций).
Применяется идемпотентно: повторный накат обновит уровни до значений
по умолчанию.
"""
from django.db import migrations

ROLE_CODE = "HR_MANAGER"
PERMISSIONS = (
    ("hr", "admin"),
    ("core", "r"),
    ("reports", "r"),
    ("ledger", "r"),
)


def seed_hr_manager(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    Module = apps.get_model("modules", "Module")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        return

    role, _ = Role.objects.update_or_create(
        organization=org,
        code=ROLE_CODE,
        defaults={
            "name": "Кадровик / Зарплатчик",
            "description": (
                "Управляет сотрудниками, графиками работы, табелями, "
                "компенсационными планами и расчётом зарплаты (ведомостями). "
                "Может просматривать отчёты и проводки по выплатам. "
                "К производственным модулям доступа не имеет."
            ),
            "is_system": True,
            "is_active": True,
        },
    )

    for module_code, level in PERMISSIONS:
        try:
            module = Module.objects.get(code=module_code)
        except Module.DoesNotExist:
            continue
        RolePermission.objects.update_or_create(
            role=role,
            module=module,
            defaults={"level": level},
        )


def revoke_hr_manager(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")

    try:
        org = Organization.objects.get(code="DEFAULT")
        role = Role.objects.get(organization=org, code=ROLE_CODE)
    except (Organization.DoesNotExist, Role.DoesNotExist):
        return
    RolePermission.objects.filter(role=role).delete()
    role.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0007_seed_hr_role_permission"),
    ]

    operations = [
        migrations.RunPython(seed_hr_manager, revoke_hr_manager),
    ]
