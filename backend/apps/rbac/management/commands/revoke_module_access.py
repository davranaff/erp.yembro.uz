"""
manage.py revoke_module_access <email> <module_code> [--organization <code>] [--apply]

Закрывает доступ юзера к модулю через UserModuleAccessOverride(level=NONE).

Зачем явный override, а не удаление ролей: override побеждает любые роли,
поэтому даже если у юзера остаётся Role с этим модулем — доступа не будет.
Безопасно и обратимо (см. опцию --restore).

По умолчанию dry-run (показывает план, ничего не пишет). Реальное применение
— только с флагом --apply.

Примеры:
  # Посмотреть что будет сделано:
  manage.py revoke_module_access head_feed@yembro.uz feedlot

  # Применить во всех его активных организациях:
  manage.py revoke_module_access head_feed@yembro.uz feedlot --apply

  # Только в одной конкретной организации (если у юзера membership в нескольких):
  manage.py revoke_module_access head_feed@yembro.uz feedlot --organization DEFAULT --apply

  # Откат:
  manage.py revoke_module_access head_feed@yembro.uz feedlot --restore --apply
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Закрыть доступ юзера к модулю (UserModuleAccessOverride level=NONE). "
        "Default — dry-run; для применения добавьте --apply."
    )

    def add_arguments(self, parser):
        parser.add_argument("email", help="Email пользователя.")
        parser.add_argument(
            "module_code",
            help="Код модуля (например feedlot, matochnik, ledger).",
        )
        parser.add_argument(
            "--organization",
            default=None,
            help=(
                "Код организации. Если не задан — применяется ко всем "
                "активным membership этого юзера."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Реально применить. Без флага — dry-run.",
        )
        parser.add_argument(
            "--restore",
            action="store_true",
            help=(
                "Удалить override (восстановить доступ через роли, если они есть). "
                "Используется как откат."
            ),
        )

    def handle(self, *args, **opts):
        from apps.modules.models import Module
        from apps.organizations.models import OrganizationMembership
        from apps.rbac.models import AccessLevel, UserModuleAccessOverride
        from apps.users.models import User

        email = opts["email"]
        module_code = opts["module_code"]
        org_code = opts["organization"]
        apply = opts["apply"]
        restore = opts["restore"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f"Пользователь не найден: {email}")

        try:
            module = Module.objects.get(code=module_code)
        except Module.DoesNotExist:
            raise CommandError(f"Модуль не найден: {module_code}")

        memberships_qs = OrganizationMembership.objects.filter(
            user=user, is_active=True,
        ).select_related("organization")
        if org_code:
            memberships_qs = memberships_qs.filter(organization__code=org_code)

        memberships = list(memberships_qs)
        if not memberships:
            scope = f" в организации {org_code}" if org_code else ""
            raise CommandError(
                f"У {email} нет активных membership{scope}."
            )

        verb = "RESTORE access" if restore else "REVOKE access"
        mode = "APPLY" if apply else "DRY-RUN"
        self.stdout.write(self.style.WARNING(
            f"\n{verb} · module={module_code} · user={email} · {mode}"
        ))

        with transaction.atomic():
            for m in memberships:
                existing = UserModuleAccessOverride.objects.filter(
                    membership=m, module=module,
                ).first()

                if restore:
                    if existing:
                        line = (
                            f"  org={m.organization.code}: delete override "
                            f"(was level={existing.level})"
                        )
                        if apply:
                            existing.delete()
                            line += " · DONE"
                        self.stdout.write(line)
                    else:
                        self.stdout.write(
                            f"  org={m.organization.code}: no override · skip"
                        )
                else:
                    cur = existing.level if existing else "—"
                    line = (
                        f"  org={m.organization.code}: override "
                        f"{cur} → {AccessLevel.NONE}"
                    )
                    if apply:
                        UserModuleAccessOverride.objects.update_or_create(
                            membership=m, module=module,
                            defaults={
                                "level": AccessLevel.NONE,
                                "reason": f"manage.py revoke_module_access {email} {module_code}",
                            },
                        )
                        line += " · DONE"
                    self.stdout.write(line)

            if not apply:
                # Откатываем транзакцию явно, чтобы dry-run был чистым.
                transaction.set_rollback(True)

        if not apply:
            self.stdout.write(self.style.NOTICE(
                "\nDry-run. Нечего не записано. Добавьте --apply чтобы применить.",
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\nГотово. Юзеру нужно перезайти (или подождать ~60s react-query staleTime).",
            ))
