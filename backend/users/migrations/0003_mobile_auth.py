import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0002_securityevent")]

    operations = [
        migrations.CreateModel(
            name="MobileDevice",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(blank=True, max_length=120)),
                ("platform", models.CharField(blank=True, max_length=24)),
                ("app_version", models.CharField(blank=True, max_length=32)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("revoked", "Revoked")],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mobile_devices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-last_seen_at", "-created_at"),
                "indexes": [
                    models.Index(fields=["user", "status"], name="users_mobil_user_id_f1c9f8_idx")
                ],
            },
        ),
        migrations.CreateModel(
            name="MobileCredential",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[("access", "Access"), ("refresh", "Refresh")], max_length=12
                    ),
                ),
                ("token_digest", models.CharField(max_length=64, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("rotated_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "device",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="credentials",
                        to="users.mobiledevice",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["device", "kind", "expires_at"],
                        name="users_mobil_device__23040e_idx",
                    )
                ]
            },
        ),
    ]
