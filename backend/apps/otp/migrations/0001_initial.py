import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="OtpCode",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("phone", models.CharField(db_index=True, max_length=16)),
                ("purpose", models.CharField(db_index=True, max_length=32)),
                ("code_hash", models.CharField(max_length=64)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=5)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "requested_ip",
                    models.GenericIPAddressField(blank=True, null=True),
                ),
            ],
            options={
                "verbose_name": "OTP-код",
                "verbose_name_plural": "OTP-коды",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["phone", "purpose", "-created_at"],
                        name="otp_otpcode_phone_43008c_idx",
                    ),
                ],
            },
        ),
    ]
