from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tgbot", "0011_tgmessage"),
    ]

    operations = [
        migrations.AddField(
            model_name="tglink",
            name="notify_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
