from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0017_documenttemplate_branding"),
        ("music", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="track",
            name="audio_document",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="audio_tracks",
                to="documents.document",
            ),
        ),
    ]
