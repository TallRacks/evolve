import uuid
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("organizations", "0004_membership_permission_overrides")]
    operations = [
        migrations.CreateModel(
            name="RoleProfile",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.SlugField(max_length=80)),
                ("name", models.CharField(max_length=120)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("permissions", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(on_delete=models.deletion.PROTECT, related_name="role_profiles", to="organizations.organization")),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.AddField(
            model_name="membership", name="role_profile",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name="memberships", to="organizations.roleprofile"),
        ),
        migrations.AddConstraint(model_name="roleprofile", constraint=models.UniqueConstraint(fields=("organization", "key"), name="unique_org_role_profile_key")),
    ]
