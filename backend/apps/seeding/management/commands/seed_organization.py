"""
Management command для применения core-fixture к организации.

Примеры:
    # Стандартный набор для DEFAULT-org
    python manage.py seed_organization DEFAULT

    # Кастомный YAML
    python manage.py seed_organization DEMO-FARM --config /path/to/config.yaml

    # По UUID вместо code
    python manage.py seed_organization --org-id <uuid>

    # Холостой прогон (показать счётчики, ничего не писать)
    python manage.py seed_organization DEFAULT --dry-run

    # Тихо (только итог)
    python manage.py seed_organization DEFAULT --quiet
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.organizations.models import Organization
from apps.seeding.services.loader import OrganizationSeeder, SeedError


class Command(BaseCommand):
    help = "Применить core-fixture (план счетов, склады, блоки, номенклатуру) к организации."

    def add_arguments(self, parser):
        parser.add_argument(
            "org_code",
            nargs="?",
            help="Код организации (Organization.code). Альтернатива: --org-id.",
        )
        parser.add_argument(
            "--org-id",
            help="UUID организации (альтернатива позиционному org_code).",
        )
        parser.add_argument(
            "--config",
            help=(
                "Путь к YAML-конфигу. По умолчанию apps/seeding/seeds/default_org.yaml."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Прогон без записи в БД (транзакция откатывается).",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Не печатать построчный отчёт, только итоговый JSON.",
        )

    def handle(self, *args, **options):
        org = self._resolve_org(options)
        config_path = options.get("config")
        if config_path:
            config_path = Path(config_path)
            if not config_path.exists():
                raise CommandError(f"Config not found: {config_path}")

        if not options["quiet"]:
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"Сидинг для организации: {org.code} · {org.name}"
                )
            )
            self.stdout.write(f"  Config: {config_path or '<default>'}")
            if options["dry_run"]:
                self.stdout.write(self.style.WARNING("  DRY-RUN — изменения не сохранятся."))
            self.stdout.write("")

        seeder = OrganizationSeeder(
            org,
            config_path=config_path,
            dry_run=options["dry_run"],
        )

        try:
            report = seeder.run()
        except SeedError as exc:
            raise CommandError(f"Ошибка сидинга: {exc}")

        # Итоговый JSON всегда печатаем
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Готово · создано {report.total_created()}, обновлено {report.total_updated()}"
        ))
        self.stdout.write(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))

        if report.skipped and not options["quiet"]:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(f"Пропущено ({len(report.skipped)}):"))
            for s in report.skipped:
                self.stdout.write(f"  · {s}")

        if report.errors:
            for e in report.errors:
                self.stderr.write(self.style.ERROR(f"  ! {e}"))

    def _resolve_org(self, options) -> Organization:
        org_id = options.get("org_id")
        org_code = options.get("org_code")

        if not (org_id or org_code):
            raise CommandError(
                "Укажите org_code позиционно или --org-id <uuid>."
            )

        try:
            if org_id:
                return Organization.objects.get(pk=org_id)
            return Organization.objects.get(code=org_code)
        except Organization.DoesNotExist as exc:
            raise CommandError(f"Организация не найдена: {org_code or org_id}") from exc
