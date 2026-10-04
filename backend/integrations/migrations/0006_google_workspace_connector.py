import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import integrations.validation


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("integrations", "0005_secret_backends"),
    ]

    operations = [
        migrations.CreateModel(
            name="GoogleWorkspaceConnector",
            fields=[
                ("id", models.UUIDField(default=__import__("uuid").uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                ("products", models.JSONField(default=list)),
                ("secret_backend", models.CharField(choices=[("environment", "Environment reference"), ("vault", "HashiCorp Vault"), ("aws_secrets_manager", "AWS Secrets Manager")], default="environment", max_length=24)),
                ("client_id_reference", models.CharField(max_length=220, validators=[integrations.validation.validate_google_secret_reference])),
                ("client_secret_reference", models.CharField(max_length=220, validators=[integrations.validation.validate_google_secret_reference])),
                ("redirect_uri", models.URLField(blank=True, max_length=500)),
                ("is_active", models.BooleanField(default=False)),
                ("connection_status", models.CharField(choices=[("never_tested", "Never tested"), ("healthy", "Healthy"), ("failed", "Failed")], default="never_tested", max_length=20)),
                ("last_tested_at", models.DateTimeField(blank=True, null=True)),
                ("last_test_message", models.CharField(blank=True, max_length=240)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("name",)},
        ),
    ]
