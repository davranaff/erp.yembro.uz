"""
Переименовать `PeriodicTask.task` для расписания CBU sync.

Было: `apps.currency.sync_cbu_rates` (несимметрично с именем функции)
Стало: `apps.currency.sync_cbu_rates_task` (как функция в коде)

Без этой миграции после переименования `@shared_task(name=...)` cron-расписание
ссылалось бы на несуществующее имя — Celery бы не нашёл задачу и rates перестали
бы синхронизироваться.
"""
from django.db import migrations


TASK_NAME = "cbu-daily-sync"
OLD_PATH = "apps.currency.sync_cbu_rates"
NEW_PATH = "apps.currency.sync_cbu_rates_task"


def forward(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=TASK_NAME, task=OLD_PATH).update(task=NEW_PATH)


def backward(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=TASK_NAME, task=NEW_PATH).update(task=OLD_PATH)


class Migration(migrations.Migration):
    dependencies = [
        ("currency", "0004_integrationsynclog"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
