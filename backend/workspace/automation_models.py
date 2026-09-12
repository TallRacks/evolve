import uuid

from django.db import models

from core.models import TimestampedModel


class AutomationExecution(TimestampedModel):
    class Status(models.TextChoices):
        EXECUTED = "executed", "Executed"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    automation = models.ForeignKey("workspace.Automation", on_delete=models.PROTECT, related_name="executions")
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    event_key = models.CharField(max_length=80)
    correlation_id = models.UUIDField()
    depth = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices)
    result_summary = models.CharField(max_length=500, blank=True)
    idempotency_key = models.CharField(max_length=180, unique=True)
