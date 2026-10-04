import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0013_presentation_format"),
        ("users", "0004_user_profile_image_url_user_username"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="profile_image_document",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="profile_image_users",
                to="documents.document",
            ),
        ),
    ]
