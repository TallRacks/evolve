import uuid

from django.conf import settings
from django.db import models

from core.models import TimestampedModel


class MobileDevice(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mobile_devices"
    )
    name = models.CharField(max_length=120, blank=True)
    platform = models.CharField(max_length=24, blank=True)
    app_version = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-last_seen_at", "-created_at")
        indexes = [models.Index(fields=("user", "status"))]


class MobileCredential(TimestampedModel):
    class Kind(models.TextChoices):
        ACCESS = "access", "Access"
        REFRESH = "refresh", "Refresh"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(MobileDevice, on_delete=models.CASCADE, related_name="credentials")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    rotated_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=("device", "kind", "expires_at"))]

    @property
    def usable(self):
        from django.utils import timezone

        return (
            self.revoked_at is None
            and self.rotated_at is None
            and self.expires_at > timezone.now()
            and self.device.status == MobileDevice.Status.ACTIVE
            and self.device.user.is_active
        )
