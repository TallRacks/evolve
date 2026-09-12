import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("organizations", "0002_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="AIProviderConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider_name", models.CharField(max_length=80)), ("model", models.CharField(max_length=120)),
                ("secret_reference", models.CharField(blank=True, max_length=110)), ("is_active", models.BooleanField(default=False)),
                ("status", models.CharField(default="not_configured", max_length=24)), ("last_tested_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Automation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=160)), ("event_key", models.CharField(max_length=80)),
                ("condition", models.JSONField(blank=True, default=dict)), ("action_key", models.CharField(max_length=80)),
                ("action_config", models.JSONField(blank=True, default=dict)), ("is_active", models.BooleanField(default=False)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organizations.organization")),
            ],
        ),
        migrations.CreateModel(
            name="ActionRequest",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("channel", models.CharField(default="copilot", max_length=32)), ("action_key", models.CharField(max_length=80)),
                ("risk", models.CharField(choices=[("read", "Read only"), ("low", "Low risk"), ("medium", "Medium risk"), ("high", "High risk")], max_length=16)),
                ("validated_payload", models.JSONField(default=dict)), ("status", models.CharField(choices=[("proposed", "Proposed"), ("executed", "Executed"), ("cancelled", "Cancelled"), ("expired", "Expired"), ("failed", "Failed"), ("blocked", "Blocked")], default="proposed", max_length=16)),
                ("confirmation_hash", models.CharField(blank=True, max_length=64)), ("expires_at", models.DateTimeField()), ("executed_at", models.DateTimeField(blank=True, null=True)),
                ("result_summary", models.CharField(blank=True, max_length=500)), ("idempotency_key", models.CharField(max_length=160, unique=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organizations.organization")),
            ],
            options={"indexes": [models.Index(fields=["organization", "status", "expires_at"], name="workspace_a_organiz_d6b541_idx")]},
        ),
    ]
