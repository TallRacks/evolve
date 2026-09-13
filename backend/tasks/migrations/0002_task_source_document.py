import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0010_officedocumentattachment"), ("tasks", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="task",
            name="source_document",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="source_tasks",
                to="documents.document",
            ),
        ),
    ]
