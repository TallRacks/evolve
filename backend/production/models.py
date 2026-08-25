import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as error:
        raise ValidationError("Use a valid IANA timezone identifier.") from error


def valid_membership(membership, organization_id):
    return (
        membership.organization_id == organization_id
        and membership.is_active
        and membership.user.is_active
        and membership.organization.is_active
    )


class ProductionAdvance(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_PROGRESS = "in_progress", "In progress"
        READY = "ready", "Ready"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="production_advances"
    )
    booking = models.OneToOneField(
        "bookings.Booking", on_delete=models.PROTECT, related_name="production_advance"
    )
    artist = models.ForeignKey(
        "artists.Artist", on_delete=models.PROTECT, related_name="production_advances"
    )
    venue = models.ForeignKey(
        "venues.Venue",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="production_advances",
    )
    promoter = models.ForeignKey(
        "promoters.Promoter",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="production_advances",
    )
    production_title = models.CharField(max_length=220)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    production_notes = models.TextField(blank=True, max_length=5000)
    access_notes = models.TextField(blank=True, max_length=5000)
    parking_notes = models.TextField(blank=True, max_length=5000)
    security_notes = models.TextField(blank=True, max_length=5000)
    advance_due_at = models.DateTimeField(null=True, blank=True)
    last_advanced_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="production_advances_created",
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("booking__event_date", "production_title")
        indexes = [models.Index(fields=("organization", "status", "advance_due_at"))]

    def clean(self):
        if self.booking_id:
            if self.booking.organization_id != self.organization_id:
                raise ValidationError(
                    {"booking": "Booking and advance must belong to the same organization."}
                )
            if self.booking.artist_id != self.artist_id:
                raise ValidationError({"artist": "Advance Artist must match the Booking Artist."})
        if self.artist_id and self.artist.organization_id != self.organization_id:
            raise ValidationError(
                {"artist": "Artist and advance must belong to the same organization."}
            )
        for field in ("venue", "promoter"):
            value = getattr(self, field)
            if value and value.organization_id != self.organization_id:
                raise ValidationError(
                    {field: f"{field.title()} and advance must belong to the same organization."}
                )

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if old and old != self.status:
                raise ValidationError(
                    "Use the Production Advance lifecycle service to change status."
                )
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Production Advances cannot be deleted; archive them instead.")

    def __str__(self):
        return self.production_title


class AdvanceRequirement(TimestampedModel):
    class Category(models.TextChoices):
        TECHNICAL = "technical", "Technical"
        HOSPITALITY = "hospitality", "Hospitality"
        BACKLINE = "backline", "Backline"
        STAGE = "stage", "Stage"
        AUDIO = "audio", "Audio"
        LIGHTING = "lighting", "Lighting"
        VIDEO = "video", "Video"
        POWER = "power", "Power"
        SECURITY = "security", "Security"
        ACCESS = "access", "Access"
        PARKING = "parking", "Parking"
        CATERING = "catering", "Catering"
        DRESSING_ROOM = "dressing_room", "Dressing room"
        MERCHANDISE = "merchandise", "Merchandise"
        GUEST_LIST = "guest_list", "Guest list"
        TRANSPORT = "transport", "Transport"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REQUESTED = "requested", "Requested"
        IN_PROGRESS = "in_progress", "In progress"
        CONFIRMED = "confirmed", "Confirmed"
        NOT_APPLICABLE = "not_applicable", "Not applicable"
        BLOCKED = "blocked", "Blocked"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Source(models.TextChoices):
        ARTIST = "artist", "Artist"
        VENUE = "venue", "Venue"
        PROMOTER = "promoter", "Promoter"
        MANAGEMENT = "management", "Management"
        PRODUCTION = "production", "Production"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    advance = models.ForeignKey(
        ProductionAdvance, on_delete=models.PROTECT, related_name="requirements"
    )
    category = models.CharField(max_length=30, choices=Category.choices)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, max_length=5000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.PRODUCTION)
    response_notes = models.TextField(blank=True, max_length=5000)
    due_at = models.DateTimeField(null=True, blank=True)
    sequence = models.PositiveIntegerField(default=1)
    assigned_membership = models.ForeignKey(
        "organizations.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="production_requirements",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="production_requirements_created",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sequence", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("advance", "sequence"),
                condition=Q(is_active=True),
                name="unique_active_requirement_sequence",
            )
        ]

    def clean(self):
        if self.assigned_membership_id and not valid_membership(
            self.assigned_membership, self.advance.organization_id
        ):
            raise ValidationError(
                {
                    "assigned_membership": (
                        "Assignee must be an access-valid membership in this organization."
                    )
                }
            )

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if old and old != self.status:
                raise ValidationError("Use the requirement status service.")
        self.full_clean()
        super().save(*args, **kwargs)


class ProductionContactAssignment(TimestampedModel):
    class Role(models.TextChoices):
        PROMOTER = "promoter", "Promoter"
        VENUE = "venue", "Venue"
        PRODUCTION_MANAGER = "production_manager", "Production manager"
        TECHNICAL_MANAGER = "technical_manager", "Technical manager"
        STAGE_MANAGER = "stage_manager", "Stage manager"
        SOUND = "sound", "Sound"
        LIGHTING = "lighting", "Lighting"
        SECURITY = "security", "Security"
        HOSPITALITY = "hospitality", "Hospitality"
        CATERING = "catering", "Catering"
        TRANSPORT = "transport", "Transport"
        MERCHANDISE = "merchandise", "Merchandise"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    advance = models.ForeignKey(
        ProductionAdvance, on_delete=models.PROTECT, related_name="contact_assignments"
    )
    contact = models.ForeignKey(
        "contacts.Contact", on_delete=models.PROTECT, related_name="production_assignments"
    )
    role = models.CharField(max_length=30, choices=Role.choices)
    responsibility = models.CharField(max_length=220, blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, max_length=3000)

    class Meta:
        ordering = ("-is_primary", "role", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("advance", "role"),
                condition=Q(is_primary=True, is_active=True),
                name="one_primary_production_contact_per_role",
            )
        ]

    def clean(self):
        if self.contact_id and self.contact.organization_id != self.advance.organization_id:
            raise ValidationError(
                {"contact": "Contact and advance must belong to the same organization."}
            )
        if self.is_active and self.contact_id and not self.contact.is_active:
            raise ValidationError({"contact": "Inactive Contacts cannot be assigned."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ProductionScheduleItem(TimestampedModel):
    class Type(models.TextChoices):
        VENUE_ACCESS = "venue_access", "Venue access"
        LOAD_IN = "load_in", "Load in"
        SOUNDCHECK = "soundcheck", "Soundcheck"
        LINE_CHECK = "line_check", "Line check"
        REHEARSAL = "rehearsal", "Rehearsal"
        CATERING = "catering", "Catering"
        DOORS = "doors", "Doors"
        SUPPORT = "support", "Support"
        SHOW = "show", "Show"
        CURFEW = "curfew", "Curfew"
        LOAD_OUT = "load_out", "Load out"
        DEPARTURE = "departure", "Departure"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    advance = models.ForeignKey(
        ProductionAdvance, on_delete=models.PROTECT, related_name="schedule_items"
    )
    title = models.CharField(max_length=220)
    item_type = models.CharField(max_length=30, choices=Type.choices)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64, validators=[validate_timezone])
    location = models.CharField(max_length=220, blank=True)
    notes = models.TextField(blank=True, max_length=3000)
    sequence = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sequence", "starts_at")
        constraints = [
            models.UniqueConstraint(
                fields=("advance", "sequence"),
                condition=Q(is_active=True),
                name="unique_active_production_schedule_sequence",
            )
        ]

    def clean(self):
        if self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "End must be after start."})

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if old and old != self.status:
                raise ValidationError("Use the schedule status service.")
        self.full_clean()
        super().save(*args, **kwargs)


class AdvanceChecklistItem(TimestampedModel):
    class Category(models.TextChoices):
        GENERAL = "general", "General"
        TECHNICAL = "technical", "Technical"
        HOSPITALITY = "hospitality", "Hospitality"
        TRAVEL = "travel", "Travel"
        VENUE = "venue", "Venue"
        PROMOTER = "promoter", "Promoter"
        DOCUMENTS = "documents", "Documents"
        FINANCE = "finance", "Finance"
        SHOW_DAY = "show_day", "Show day"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    advance = models.ForeignKey(
        ProductionAdvance, on_delete=models.PROTECT, related_name="checklist_items"
    )
    title = models.CharField(max_length=220)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.GENERAL)
    is_completed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="production_checklist_completions",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    assigned_membership = models.ForeignKey(
        "organizations.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="production_checklist_items",
    )
    due_at = models.DateTimeField(null=True, blank=True)
    sequence = models.PositiveIntegerField(default=1)
    notes = models.TextField(blank=True, max_length=3000)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sequence", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("advance", "sequence"),
                condition=Q(is_active=True),
                name="unique_active_checklist_sequence",
            )
        ]

    def clean(self):
        if self.assigned_membership_id and not valid_membership(
            self.assigned_membership, self.advance.organization_id
        ):
            raise ValidationError(
                {
                    "assigned_membership": (
                        "Assignee must be an access-valid membership in this organization."
                    )
                }
            )
        if self.is_completed and not (self.completed_by_id and self.completed_at):
            raise ValidationError("Completed checklist items require an actor and completion time.")
        if not self.is_completed and (self.completed_by_id or self.completed_at):
            raise ValidationError("Open checklist items cannot retain completion metadata.")

    def save(self, *args, **kwargs):
        if self.pk:
            old = (
                type(self).objects.filter(pk=self.pk).values_list("is_completed", flat=True).first()
            )
            if old is not None and old != self.is_completed:
                raise ValidationError("Use the checklist completion service.")
        self.full_clean()
        super().save(*args, **kwargs)
