import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("artists", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="ArtistToolkit",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("short_bio", models.TextField(blank=True, max_length=1500)),
                ("long_bio", models.TextField(blank=True, max_length=6000)),
                ("rate_card", models.TextField(blank=True, max_length=6000)),
                ("stats_summary", models.TextField(blank=True, max_length=4000)),
                ("artist", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="toolkit", to="artists.artist")),
            ],
        ),
    ]
