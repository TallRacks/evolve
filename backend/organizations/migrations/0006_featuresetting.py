from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [("organizations", "0005_roleprofile_membership_role_profile_and_more")]
    operations = [
        migrations.CreateModel(
            name="FeatureSetting",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.SlugField(max_length=100)),
                ("label", models.CharField(max_length=140)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("is_enabled", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="feature_settings", to="organizations.organization")),
            ],
            options={"ordering": ("label",), "constraints": [models.UniqueConstraint(fields=("organization", "key"), name="unique_org_feature_setting")]},
        ),
    ]
