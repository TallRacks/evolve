import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel


class SavedReportView(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="saved_report_views"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_report_views"
    )
    report_key = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    filters = models.JSONField(default=dict, blank=True)
    sort = models.CharField(max_length=40, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ("report_key", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "user", "report_key", "name"),
                name="unique_saved_report_name_per_user",
            ),
            models.UniqueConstraint(
                fields=("organization", "user", "report_key"),
                condition=Q(is_default=True),
                name="one_default_saved_report_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.report_key}: {self.name}"
