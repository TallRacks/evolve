import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0008_documentrevision_officedocumentcontent"),
        ("workspace", "0005_alter_comment_context_type"),
    ]
    operations = [
        migrations.AddField(
            model_name="document",
            name="workspace",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="documents",
                to="workspace.workspace",
            ),
        ),
    ]
