from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [("rights", "0004_royaltystatement_source_type_royaltyadvance")]
    operations = [
        migrations.CreateModel(
            name="RoyaltySource",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=220)),
                ("source_type", models.CharField(choices=[("distributor", "Distributor"), ("label", "Label"), ("publisher", "Publisher"), ("society", "Collection society"), ("other", "Other")], default="distributor", max_length=24)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True, max_length=2000)),
                ("organization", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="royalty_sources", to="organizations.organization")),
            ],
            options={"ordering": ("name",), "constraints": [models.UniqueConstraint(fields=("organization", "name"), name="unique_royalty_source_name")]},
        ),
        migrations.AddField(model_name="royaltystatement", name="source", field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name="statements", to="rights.royaltysource")),
        migrations.AddField(model_name="royaltystatementline", name="release_title", field=models.CharField(blank=True, max_length=220)),
        migrations.AddField(model_name="royaltystatementline", name="upc_ean", field=models.CharField(blank=True, max_length=14)),
        migrations.AddField(model_name="royaltystatementline", name="isrc", field=models.CharField(blank=True, max_length=12)),
    ]
