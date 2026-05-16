from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tgbot", "0011_tgmessage"),
    ]

    operations = [
        # Column was added manually via ALTER TABLE before this migration ran.
        # Use RunSQL with IF NOT EXISTS so re-running on prod doesn't crash.
        migrations.RunSQL(
            sql="ALTER TABLE tgbot_tglink ADD COLUMN IF NOT EXISTS notify_enabled boolean NOT NULL DEFAULT false;",
            reverse_sql="ALTER TABLE tgbot_tglink DROP COLUMN IF EXISTS notify_enabled;",
            state_operations=[
                migrations.AddField(
                    model_name="tglink",
                    name="notify_enabled",
                    field=models.BooleanField(default=False),
                ),
            ],
        ),
    ]
