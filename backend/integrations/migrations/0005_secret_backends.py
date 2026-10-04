from django.db import migrations, models

import integrations.validation


class Migration(migrations.Migration):
    dependencies = [("integrations", "0004_seed_storage_policy")]

    operations = [
        migrations.AddField(
            model_name="emailconnector",
            name="secret_backend",
            field=models.CharField(
                choices=[
                    ("environment", "Environment reference"),
                    ("vault", "HashiCorp Vault"),
                    ("aws_secrets_manager", "AWS Secrets Manager"),
                ],
                default="environment",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="storageprovider",
            name="secret_backend",
            field=models.CharField(
                choices=[
                    ("environment", "Environment reference"),
                    ("vault", "HashiCorp Vault"),
                    ("aws_secrets_manager", "AWS Secrets Manager"),
                ],
                default="environment",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="emailconnector",
            name="secret_reference",
            field=models.CharField(
                max_length=220,
                validators=[integrations.validation.validate_email_secret_reference],
            ),
        ),
        migrations.AlterField(
            model_name="storageprovider",
            name="access_key_reference",
            field=models.CharField(
                max_length=220,
                validators=[integrations.validation.validate_storage_secret_reference],
            ),
        ),
        migrations.AlterField(
            model_name="storageprovider",
            name="secret_key_reference",
            field=models.CharField(
                max_length=220,
                validators=[integrations.validation.validate_storage_secret_reference],
            ),
        ),
    ]
