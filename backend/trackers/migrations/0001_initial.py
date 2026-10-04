import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = [("organizations", "0004_membership_permission_overrides"), ("integrations", "0006_google_workspace_connector"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="Tracker", fields=[
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("name", models.CharField(max_length=180)), ("kind", models.CharField(choices=[("bookings","Bookings"),("tasks","Tasks"),("events","Events"),("releases","Releases")], max_length=20)),
            ("spreadsheet_id", models.CharField(max_length=220)), ("worksheet_name", models.CharField(default="Sheet1", max_length=180)),
            ("direction", models.CharField(choices=[("sheet_source","Spreadsheet is source of truth"),("evolve_source","Evolve is source of truth")], default="sheet_source", max_length=20)),
            ("field_mapping", models.JSONField(blank=True, default=dict)), ("last_synced_at", models.DateTimeField(blank=True, null=True)),
            ("last_sync_status", models.CharField(default="never", max_length=20)), ("last_sync_message", models.CharField(blank=True, max_length=500)),
            ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ("google_connector", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trackers", to="integrations.googleworkspaceconnector")),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trackers", to="organizations.organization")),
        ], options={"ordering": ("kind","name")}),
        migrations.CreateModel(name="TrackerSyncEvent", fields=[
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("direction", models.CharField(choices=[("import","Import"),("export","Export")], max_length=10)), ("status", models.CharField(max_length=20)),
            ("rows_created", models.PositiveIntegerField(default=0)), ("rows_updated", models.PositiveIntegerField(default=0)), ("rows_skipped", models.PositiveIntegerField(default=0)), ("message", models.CharField(blank=True, max_length=500)),
            ("requested_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ("tracker", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sync_events", to="trackers.tracker")),
        ]),
        migrations.AddConstraint(model_name="tracker", constraint=models.UniqueConstraint(fields=("organization","kind"), name="one_tracker_kind_per_organization")),
    ]
