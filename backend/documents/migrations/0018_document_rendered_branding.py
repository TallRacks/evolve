from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0017_documenttemplate_branding")]

    operations = [
        migrations.AddField(
            model_name="document",
            name="rendered_branding",
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
    ]
