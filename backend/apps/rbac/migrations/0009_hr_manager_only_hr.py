"""
Сужаем роль HR_MANAGER до только-hr.

В миграции 0008 мы дали HR_MANAGER уровень `r` на core, reports, ledger
для удобства (чтобы кадровик мог увидеть базовые справочники и проводки
по выплатам). Но фронт показал ему пункты «Номенклатура», «План счетов»,
«Блоки», «Контрагенты», «Трассировка», «Отчёты», «Курсы валют»,
«Проводки» — это шум, HR-у эти страницы не нужны.

Здесь убираем r на core/reports/ledger. В навигации остаются только
HR-пункты (Сотрудники, Ведомости, Графики работы, Аналитика ЗП).
Сводка / Касса и банк / Токены продавцов скрываются через
requireAnyModule на фронте.

Идемпотентно — миграция убирает permissions если они есть, и ничего не
делает если их уже нет.
"""
from django.db import migrations

REVOKE_MODULES = ("core", "reports", "ledger")


def shrink_hr_manager(apps, schema_editor):
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    Organization = apps.get_model("organizations", "Organization")

    try:
        org = Organization.objects.get(code="DEFAULT")
        role = Role.objects.get(organization=org, code="HR_MANAGER")
    except (Organization.DoesNotExist, Role.DoesNotExist):
        return

    RolePermission.objects.filter(
        role=role,
        module__code__in=REVOKE_MODULES,
    ).delete()


def restore_hr_manager(apps, schema_editor):
    """Reverse: возвращаем permissions из 0008 на случай отката."""
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    Module = apps.get_model("modules", "Module")
    Organization = apps.get_model("organizations", "Organization")

    try:
        org = Organization.objects.get(code="DEFAULT")
        role = Role.objects.get(organization=org, code="HR_MANAGER")
    except (Organization.DoesNotExist, Role.DoesNotExist):
        return

    for module_code in REVOKE_MODULES:
        try:
            module = Module.objects.get(code=module_code)
        except Module.DoesNotExist:
            continue
        RolePermission.objects.update_or_create(
            role=role, module=module, defaults={"level": "r"},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0008_seed_hr_manager_role"),
    ]

    operations = [
        migrations.RunPython(shrink_hr_manager, restore_hr_manager),
    ]
