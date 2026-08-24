import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TimestampedModel


class CalendarEvent(TimestampedModel):
    class Type(models.TextChoices):
        MEETING = "meeting", "Meeting"
        REHEARSAL = "rehearsal", "Rehearsal"
        CONTENT = "content", "Content"
        PRESS = "press", "Press"
        ADMIN = "admin", "Administration"
        REMINDER = "reminder", "Reminder"
        OTHER = "other", "Other"

    class Visibility(models.TextChoices):
        ORGANIZATION = "organization", "Organization"
        ARTIST_TEAM = "artist_team", "Artist team"
        PRIVATE = "private", "Private"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CANCELLED = "cancelled", "Cancelled"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="calendar_events"
    )
    title = models.CharField(max_length=220)
    event_type = models.CharField(max_length=20, choices=Type.choices)
    description = models.TextField(blank=True, max_length=5000)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    all_day = models.BooleanField(default=False)
    timezone = models.CharField(max_length=64, default="Africa/Johannesburg")
    artist = models.ForeignKey(
        "artists.Artist",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="calendar_events",
    )
    owner_membership = models.ForeignKey(
        "organizations.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="owned_calendar_events",
    )
    location = models.CharField(max_length=300, blank=True)
    visibility = models.CharField(
        max_length=20, choices=Visibility.choices, default=Visibility.ORGANIZATION
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="calendar_events_created",
    )

    class Meta:
        ordering = ("starts_at", "title")
        indexes = [models.Index(fields=("organization", "starts_at", "status"))]

    def clean(self):
        if self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "End must be after start."})
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValidationError({"timezone": "Use a valid IANA timezone."}) from exc
        if self.artist_id and self.artist.organization_id != self.organization_id:
            raise ValidationError("Event Artist must belong to the organization.")
        if self.visibility == self.Visibility.ARTIST_TEAM and not self.artist_id:
            raise ValidationError({"artist": "Artist-team events require an Artist."})
        if self.owner_membership_id and (
            self.owner_membership.organization_id != self.organization_id
            or not self.owner_membership.is_active
            or not self.owner_membership.user.is_active
        ):
            raise ValidationError(
                {"owner_membership": "Owner must be an active membership in this organization."}
            )

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if old and old != self.status:
                raise ValidationError("Use the Calendar Event lifecycle service.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Calendar events cannot be deleted; archive them instead.")
