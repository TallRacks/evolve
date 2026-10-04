import uuid

from django.conf import settings
from django.db import models

from core.models import TimestampedModel


class SigningRequest(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready to send"
        SENT = "sent", "Sent"
        VIEWED = "viewed", "Viewed"
        PARTIALLY_SIGNED = "partially_signed", "Partially signed"
        COMPLETED = "completed", "Completed"
        DECLINED = "declined", "Declined"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="signing_requests")
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.PROTECT, related_name="signing_requests")
    source_document = models.ForeignKey("documents.Document", null=True, blank=True, on_delete=models.PROTECT, related_name="signing_requests")
    source_contract = models.ForeignKey("contracts.Contract", null=True, blank=True, on_delete=models.PROTECT, related_name="signing_requests")
    title = models.CharField(max_length=220)
    template_key = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    provider = models.CharField(max_length=32, default="opensign")
    provider_document_id = models.CharField(max_length=220, blank=True)
    signing_url = models.URLField(max_length=1000, blank=True)
    completed_document_url = models.URLField(max_length=1000, blank=True)
    signers = models.JSONField(default=list)
    last_event_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="signing_requests_created")

    class Meta:
        ordering = ("-updated_at",)
        indexes = [models.Index(fields=("organization", "status"))]


class SigningEvent(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(SigningRequest, on_delete=models.PROTECT, related_name="events")
    provider_event_id = models.CharField(max_length=220, blank=True)
    event_type = models.CharField(max_length=100)
    status = models.CharField(max_length=24, choices=SigningRequest.Status.choices)
    payload_digest = models.CharField(max_length=64)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("request", "provider_event_id"), name="signing_unique_provider_event")]
