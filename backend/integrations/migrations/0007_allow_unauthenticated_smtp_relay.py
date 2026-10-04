from django.db import migrations, models

import integrations.validation


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0006_google_workspace_connector"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emailconnector",
            name="secret_reference",
            field=models.CharField(blank=True, max_length=220, validators=[integrations.validation.validate_email_secret_reference]),
        ),
    ]
