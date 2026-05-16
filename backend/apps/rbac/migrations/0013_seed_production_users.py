"""
Seed production users for the DEFAULT organisation.

Creates a HEAD_SALES role (not in 0005) and 9 users with pre-set passwords:

  ceo@yembro.uz               CEO / HEAD_ADMIN  (is_superuser)
  feed_head@yembro.uz         HEAD_SUPPLY
  feedlot_head@yembro.uz      HEAD_FEEDLOT
  matochnik_head@yembro.uz    HEAD_MATOCHNIK
  incubation_head@yembro.uz   HEAD_INCUBATION
  slaughter_head@yembro.uz    HEAD_SLAUGHTER
  vet_head@yembro.uz          HEAD_SUPPLY
  sales_head@yembro.uz        HEAD_SALES  (new role created here)
  finance_head@yembro.uz      HEAD_ACCOUNTING

Idempotent: users are update_or_create'd on email; passwords are written
only when the user is freshly created (or has no password yet).
"""
from django.contrib.auth.hashers import make_password
from django.db import migrations


HEAD_SALES_PERMISSIONS = {
    "sales": "admin",
    "slaughter": "r",   # sees finished product origin
    "stock": "r",
    "core": "rw",
    "reports": "r",
}

USER_DEFINITIONS = [
    # (email, password, full_name, role_code, position_title, is_super)
    ("ceo@yembro.uz",             "WQFYwbMOxwxsvj", "CEO",                   "HEAD_ADMIN",       "CEO",                   True),
    ("feed_head@yembro.uz",       "2vSfelx8zl9B2t", "Head of Feed",          "HEAD_SUPPLY",      "Head of Feed",          False),
    ("feedlot_head@yembro.uz",    "WSipMs2786riq0", "Head of Feedlot",       "HEAD_FEEDLOT",     "Head of Feedlot",       False),
    ("matochnik_head@yembro.uz",  "JZCwhGO1mNKnri", "Head of Matochnik",     "HEAD_MATOCHNIK",   "Head of Matochnik",     False),
    ("incubation_head@yembro.uz", "bS8theZU6Jk8E0", "Head of Incubation",    "HEAD_INCUBATION",  "Head of Incubation",    False),
    ("slaughter_head@yembro.uz",  "Mo8cj6PMmrBT9t", "Head of Slaughter",     "HEAD_SLAUGHTER",   "Head of Slaughter",     False),
    ("vet_head@yembro.uz",        "SwcgTCjENqaiAW", "Head of Vet",           "HEAD_SUPPLY",      "Head of Veterinary",    False),
    ("sales_head@yembro.uz",      "mzlyNlUbUXba1u", "Head of Sales",         "HEAD_SALES",       "Head of Sales",         False),
    ("finance_head@yembro.uz",    "9A51lK6bjhPij4", "CFO",                   "HEAD_ACCOUNTING",  "CFO",                   False),
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

    # ── Create HEAD_SALES role ────────────────────────────────────────────
    sales_role, _ = Role.objects.update_or_create(
        organization=org,
        code="HEAD_SALES",
        defaults={
            "name": "Главный отдела продаж",
            "description": "Управление продажами готовой продукции.",
            "is_system": False,
            "is_active": True,
        },
    )
    for module_code, module in modules_by_code.items():
        level = HEAD_SALES_PERMISSIONS.get(module_code, "none")
        RolePermission.objects.update_or_create(
            role=sales_role,
            module=module,
            defaults={"level": level},
        )

    # ── Create users and assign roles ─────────────────────────────────────
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

        role = Role.objects.get(organization=org, code=role_code)
        UserRole.objects.get_or_create(membership=membership, role=role)


def reverse(apps, schema_editor):
    User = apps.get_model("users", "User")
    Role = apps.get_model("rbac", "Role")
    UserRole = apps.get_model("rbac", "UserRole")

    emails = [row[0] for row in USER_DEFINITIONS]
    UserRole.objects.filter(role__code="HEAD_SALES").delete()
    Role.objects.filter(code="HEAD_SALES").delete()
    User.objects.filter(email__in=emails).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0012_seed_hr_for_head_admin"),
        ("users", "0002_userfavoritepage"),
        ("organizations", "0004_rename_default_org_name"),
        ("modules", "0007_seed_hr_module"),
    ]

    operations = [
        migrations.RunPython(seed, reverse),
    ]
