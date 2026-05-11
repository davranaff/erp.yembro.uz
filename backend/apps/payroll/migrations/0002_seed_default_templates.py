"""
Сидер дефолтных шаблонов графика для DEFAULT-org:
    - STD-9-18  — пн-пт 9:00-18:00
    - SHIFT-2-2 — 2/2 по 12 часов
"""
from django.db import migrations


def seed_templates(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    WorkScheduleTemplate = apps.get_model("payroll", "WorkScheduleTemplate")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        return

    WorkScheduleTemplate.objects.update_or_create(
        organization=org, code="STD-9-18",
        defaults={
            "name": "Стандарт пн-пт 9-18",
            "pattern_kind": "weekday_mask",
            "pattern": {
                "weekdays": [0, 1, 2, 3, 4],
                "start": "09:00",
                "end": "18:00",
                "duration_hours": 8,
            },
            "is_active": True,
        },
    )
    WorkScheduleTemplate.objects.update_or_create(
        organization=org, code="SHIFT-2-2",
        defaults={
            "name": "Сменный 2/2 по 12 часов",
            "pattern_kind": "rotation",
            "pattern": {
                "work_days": 2,
                "rest_days": 2,
                "anchor_date": "2026-01-01",
                "start": "08:00",
                "end": "20:00",
                "duration_hours": 12,
            },
            "is_active": True,
        },
    )


def unseed_templates(apps, schema_editor):
    WorkScheduleTemplate = apps.get_model("payroll", "WorkScheduleTemplate")
    WorkScheduleTemplate.objects.filter(
        code__in=["STD-9-18", "SHIFT-2-2"]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
