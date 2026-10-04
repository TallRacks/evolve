import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from core.models import TimestampedModel

class Tracker(TimestampedModel):
    class Kind(models.TextChoices):
        BOOKINGS = "bookings", "Bookings"
        TASKS = "tasks", "Tasks"
        EVENTS = "events", "Events"
        RELEASES = "releases", "Releases"
    class Direction(models.TextChoices):
        SHEET_SOURCE = "sheet_source", "Spreadsheet is source of truth"
        EVOLVE_SOURCE = "evolve_source", "Evolve is source of truth"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="trackers")
    google_connector = models.ForeignKey("integrations.GoogleWorkspaceConnector", on_delete=models.PROTECT, related_name="trackers")
    name = models.CharField(max_length=180)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    spreadsheet_id = models.CharField(max_length=220)
    worksheet_name = models.CharField(max_length=180, default="Sheet1")
    direction = models.CharField(max_length=20, choices=Direction.choices, default=Direction.SHEET_SOURCE)
    field_mapping = models.JSONField(default=dict, blank=True)
    schema_state = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=20, default="never")
    last_sync_message = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    class Meta:
        ordering = ("kind", "name")
        constraints = [models.UniqueConstraint(fields=("organization", "kind"), name="one_tracker_kind_per_organization")]
    def clean(self):
        if self.google_connector and "sheets" not in (self.google_connector.products or []):
            raise ValidationError({"google_connector": "The selected Google connector must include Sheets."})
        if not isinstance(self.field_mapping, dict):
            raise ValidationError({"field_mapping": "Field mapping must be an object."})

class TrackerSyncEvent(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tracker = models.ForeignKey(Tracker, on_delete=models.PROTECT, related_name="sync_events")
    direction = models.CharField(max_length=10, choices=(("import", "Import"), ("export", "Export")))
    status = models.CharField(max_length=20)
    rows_created = models.PositiveIntegerField(default=0)
    rows_updated = models.PositiveIntegerField(default=0)
    rows_skipped = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=500, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
