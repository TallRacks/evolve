import uuid

from django.db import models

from core.models import TimestampedModel


class Contact(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="contacts"
    )
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    job_title = models.CharField(max_length=160, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    mobile = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True, max_length=5000)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("last_name", "first_name")
        indexes = [models.Index(fields=("organization", "is_active"))]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.full_name
