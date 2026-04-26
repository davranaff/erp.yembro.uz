"""
Сидинг 7 демо-ролей и 7 демо-пользователей в организации DEFAULT.

Структура:
- 1 главный администратор (HEAD_ADMIN) с полными правами на все 13 модулей.
- 6 руководителей профильных направлений: маточник, инкубация, откорм,
  убойня, корма+вет, бухгалтерия. Каждый получает admin на свой модуль и
  разумный read/write на смежные модули в производственной цепочке.

Идемпотентно:
- Пользователи: update_or_create по email; **существующие пароли не
  перезаписываются** (защита от случайного сброса в живой среде).
- Роли: update_or_create.
- Permissions: update_or_create — `level` синхронизируется с этой миграцией.
- Memberships, UserRole: get_or_create.

⚠️ Это **demo/dev seed**. Пароли захардкожены. Перед production — обернуть
в env-flag или вынести в management command.
"""
from django.contrib.auth.hashers import make_password
from django.db import migrations


# ─── Матрица ролей ────────────────────────────────────────────────────
# Permissions dict: {module_code: 'none'|'r'|'rw'|'admin'}.
# Любой модуль, не упомянутый в dict, получает level='none' (явный «запрет»).

ROLE_DEFINITIONS = [
    {
        "code": "HEAD_ADMIN",
        "name": "Главный администратор",
        "description": "Полный доступ ко всем модулям системы.",
        "permissions": {  # все 13 модулей = admin
            "core": "admin", "matochnik": "admin", "incubation": "admin",
            "feedlot": "admin", "slaughter": "admin", "feed": "admin",
            "vet": "admin", "stock": "admin", "ledger": "admin",
            "reports": "admin", "purchases": "admin", "sales": "admin",
            "admin": "admin",
        },
    },
    {
        "code": "HEAD_MATOCHNIK",
        "name": "Главный маточника",
        "description": "Управление родительским стадом, яйцесбором, вакцинациями.",
        "permissions": {
            "matochnik": "admin",
            "core": "rw",          # справочники: контрагенты/SKU/блоки
            "feed": "r",           # видит сколько корма пошло
            "vet": "r",            # видит вакцинации/лечения
            "stock": "r",
            "purchases": "r",
            "ledger": "r",
            "reports": "r",
        },
    },
    {
        "code": "HEAD_INCUBATION",
        "name": "Главный инкубации",
        "description": "Закладки яиц, овоскопия, выводы цыплят.",
        "permissions": {
            "incubation": "admin",
            "matochnik": "r",      # откуда пришли яйца
            "core": "rw",
            "stock": "r",
            "ledger": "r",
            "reports": "r",
        },
    },
    {
        "code": "HEAD_FEEDLOT",
        "name": "Главный фабрики откорма",
        "description": "Партии бройлера, кормление, FCR, падёж, отгрузки на убой.",
        "permissions": {
            "feedlot": "admin",
            "incubation": "r",     # откуда пришли цыплята
            "feed": "r",           # потребление кормов
            "vet": "r",            # лечения
            "core": "rw",
            "stock": "r",
            "ledger": "r",
            "reports": "r",
        },
    },
    {
        "code": "HEAD_SLAUGHTER",
        "name": "Главный убойни",
        "description": "Смены разделки, выход тушки, контроль качества.",
        "permissions": {
            "slaughter": "admin",
            "feedlot": "r",        # откуда пришли птицы
            "sales": "rw",         # продажа готовой продукции
            "core": "rw",
            "stock": "r",
            "ledger": "r",
            "reports": "r",
        },
    },
    {
        "code": "HEAD_SUPPLY",
        "name": "Главный кормов и вет.аптеки",
        "description": "Рецептура комбикорма, ветеринарный склад, закупки.",
        "permissions": {
            "feed": "admin",
            "vet": "admin",
            "purchases": "rw",     # сами закупают сырьё/препараты
            "stock": "rw",
            "matochnik": "r",
            "incubation": "r",
            "feedlot": "r",
            "slaughter": "r",
            "core": "rw",
            "ledger": "r",
            "reports": "r",
        },
    },
    {
        "code": "HEAD_ACCOUNTING",
        "name": "Главный бухгалтерии",
        "description": "Закупки, продажи, проводки, отчёты, склад. Read на производство.",
        "permissions": {
            "ledger": "admin",
            "reports": "admin",
            "sales": "admin",
            "purchases": "admin",
            "stock": "admin",
            "matochnik": "r",
            "incubation": "r",
            "feedlot": "r",
            "slaughter": "r",
            "feed": "r",
            "vet": "r",
            "core": "rw",
            "admin": "r",          # доступ на просмотр аудита/ролей
        },
    },
]


# ─── Демо-пользователи ────────────────────────────────────────────────
# email · password · full_name · role_code · position_title · is_super
# Пароли соответствуют дефолтному validate_password (длина ≥ 8, смесь регистра/цифр/символа).

USER_DEFINITIONS = [
    ("admin@yembro.uz",       "Admin2026!",       "Admin User",          "HEAD_ADMIN",       "Генеральный директор",       True),
    ("matochnik@yembro.uz",   "Matochnik2026!",   "Matochnik Manager",   "HEAD_MATOCHNIK",   "Руководитель маточника",     False),
    ("incubation@yembro.uz",  "Incubation2026!",  "Incubation Manager",  "HEAD_INCUBATION",  "Руководитель инкубации",     False),
    ("feedlot@yembro.uz",     "Feedlot2026!",     "Feedlot Manager",     "HEAD_FEEDLOT",     "Руководитель откорма",       False),
    ("slaughter@yembro.uz",   "Slaughter2026!",   "Slaughter Manager",   "HEAD_SLAUGHTER",   "Руководитель убойни",        False),
    ("supply@yembro.uz",      "Supply2026!",      "Supply Manager",      "HEAD_SUPPLY",      "Руководитель снабжения",     False),
    ("accounting@yembro.uz",  "Accounting2026!",  "Accounting Manager",  "HEAD_ACCOUNTING",  "Главный бухгалтер",          False),
]


def seed(apps, schema_editor):
    User = apps.get_model("users", "User")
    Organization = apps.get_model("organizations", "Organization")
    OrganizationMembership = apps.get_model("organizations", "OrganizationMembership")
    Module = apps.get_model("modules", "Module")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    UserRole = apps.get_model("rbac", "UserRole")

    org = Organization.objects.get(code="DEFAULT")
    modules_by_code = {m.code: m for m in Module.objects.all()}

    # ─── Создание ролей ──────────────────────────────────────────────
    roles_by_code: dict[str, object] = {}
    for definition in ROLE_DEFINITIONS:
        role, _ = Role.objects.update_or_create(
            organization=org,
            code=definition["code"],
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                # Пометка is_system=False — это пользовательские шаблоны для
                # демо, их можно править/удалять через UI на /roles.
                "is_system": False,
                "is_active": True,
            },
        )
        roles_by_code[definition["code"]] = role

        # Применяем permissions: для каждого модуля выставляем уровень из
        # dict либо 'none' если не упомянут.
        perms = definition["permissions"]
        for module_code, module in modules_by_code.items():
            level = perms.get(module_code, "none")
            RolePermission.objects.update_or_create(
                role=role,
                module=module,
                defaults={"level": level},
            )

    # ─── Создание пользователей и назначение ролей ───────────────────
    for email, password, full_name, role_code, position, is_super in USER_DEFINITIONS:
        user, created = User.objects.update_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "is_active": True,
                "is_staff": is_super,
                "is_superuser": is_super,
            },
        )
        # Пароль ставим только при создании; не перезаписываем для
        # существующих пользователей (могли поменять через UI).
        if created or not user.password:
            user.password = make_password(password)
            user.save(update_fields=["password"])

        membership, _ = OrganizationMembership.objects.get_or_create(
            user=user,
            organization=org,
            defaults={
                "is_active": True,
                "position_title": position,
                "work_status": "active",
            },
        )

        role = roles_by_code[role_code]
        UserRole.objects.get_or_create(
            membership=membership,
            role=role,
        )


def reverse(apps, schema_editor):
    """Откат: удаляем все демо-роли HEAD_* и юзеров @yembro.uz.

    Порядок важен: UserRole.role имеет on_delete=PROTECT, поэтому
    UserRole удаляем явно перед Role. Membership и RolePermission
    каскадно удаляются с User/Role (on_delete=CASCADE).
    """
    User = apps.get_model("users", "User")
    Role = apps.get_model("rbac", "Role")
    UserRole = apps.get_model("rbac", "UserRole")

    UserRole.objects.filter(role__code__startswith="HEAD_").delete()
    Role.objects.filter(code__startswith="HEAD_").delete()
    User.objects.filter(email__endswith="@yembro.uz").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0004_seed_sales_role_permission"),
        ("users", "0002_userfavoritepage"),
        ("organizations", "0004_rename_default_org_name"),
        ("modules", "0006_seed_sales_module"),
    ]

    operations = [
        migrations.RunPython(seed, reverse),
    ]
