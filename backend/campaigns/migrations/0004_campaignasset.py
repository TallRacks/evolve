import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0003_campaign_brand_name"),
        ("documents", "0017_documenttemplate_branding"),
    ]

    operations = [
        migrations.CreateModel(
            name="CampaignAsset",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=220)),
                ("channel", models.CharField(choices=[("instagram", "Instagram"), ("tiktok", "TikTok"), ("youtube", "YouTube"), ("x", "X"), ("facebook", "Facebook"), ("spotify", "Spotify"), ("apple_music", "Apple Music"), ("deezer", "Deezer"), ("email", "Email"), ("press", "Press"), ("radio", "Radio"), ("playlisting", "Playlisting"), ("influencers", "Influencers"), ("ooh", "Out of home"), ("live", "Live"), ("other", "Other")], max_length=30)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("pending_review", "Pending review"), ("approved", "Approved"), ("flighting", "Flighting"), ("completed", "Completed"), ("rejected", "Rejected"), ("archived", "Archived")], default="draft", max_length=20)),
                ("flight_start", models.DateField(blank=True, null=True)),
                ("flight_end", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, max_length=5000)),
                ("campaign", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="assets", to="campaigns.campaign")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="campaign_assets_created", to="users.user")),
                ("document", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name="campaign_assets", to="documents.document")),
            ],
            options={"ordering": ("flight_start", "title")},
        ),
    ]
