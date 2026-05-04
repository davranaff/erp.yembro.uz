from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vet", "0003_seed_vet_status_beat"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="vettreatmentlog",
            name="acknowledged_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="vettreatmentlog",
            name="acknowledged_by",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Менеджер модуля-цели (feedlot/matochnik/...) подтвердил, "
                    "что видел запись о применении препарата. Soft-acknowledgement: "
                    "не блокирует применение, только снимает уведомление."
                ),
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="vet_treatments_acknowledged",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="vettreatmentlog",
            index=models.Index(
                fields=["organization", "acknowledged_at"],
                name="vet_vettrea_organiz_13fbb3_idx",
            ),
        ),
    ]
