import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TimestampedModel


class Notification(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Category(models.TextChoices):
        TEAM = "team", "Team"
        BOOKINGS = "bookings", "Bookings"
        CALL_SHEETS = "call_sheets", "Call sheets"
        MUSIC = "music", "Music"
        MARKETING = "marketing", "Marketing"
        DOCUMENTS = "documents", "Documents"
        FINANCE = "finance", "Finance"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=80)
    category = models.CharField(max_length=24, choices=Category.choices)
    title = models.CharField(max_length=220)
    message = models.CharField(max_length=1000)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    source_type = models.CharField(max_length=80, blank=True)
    source_id = models.CharField(max_length=80, blank=True)
    action_url = models.CharField(max_length=500, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("organization", "created_at")),
            models.Index(fields=("category", "notification_type", "created_at")),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Notification content is immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.action_url and (
            not self.action_url.startswith("/")
            or self.action_url.startswith("//")
            or "://" in self.action_url
        ):
            raise ValidationError({"action_url": "Only internal relative paths are allowed."})

    def delete(self, *args, **kwargs):
        raise ValidationError("Notification history cannot be deleted.")


class NotificationRecipient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification, on_delete=models.PROTECT, related_name="recipients"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="notification_recipients"
    )
    read_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("notification", "user"), name="unique_notification_recipient"
            )
        ]
        indexes = [
            models.Index(fields=("user", "read_at")),
            models.Index(fields=("user", "archived_at")),
        ]

    def __str__(self):
        return f"{self.user}: {self.notification}"

    def delete(self, *args, **kwargs):
        raise ValidationError("Recipient state must be archived, not deleted.")


class NotificationPreference(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preferences"
    )
    category = models.CharField(max_length=24, choices=Notification.Category.choices)
    in_app_enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "category"), name="unique_user_notification_category"
            )
        ]
