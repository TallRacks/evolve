from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0016_alter_document_document_type")]

    operations = [
        migrations.AddField(
            model_name="documenttemplate",
            name="branding",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
