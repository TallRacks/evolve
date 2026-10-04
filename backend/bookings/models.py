import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel


def booking_reference():
    return f"EV-{uuid.uuid4().hex[:10].upper()}"


class Booking(TimestampedModel):
    class Status(models.TextChoices):
        ENQUIRY = "enquiry", "Enquiry"
        HOLD = "hold", "Hold"
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        DECLINED = "declined", "Declined"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="bookings"
    )
    reference = models.CharField(
        max_length=20, unique=True, default=booking_reference, editable=False
    )
    title = models.CharField(max_length=220)
    artist = models.ForeignKey("artists.Artist", on_delete=models.PROTECT, related_name="bookings")
    promoter = models.ForeignKey(
        "promoters.Promoter",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    venue = models.ForeignKey(
        "venues.Venue",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ENQUIRY)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    performance_type = models.CharField(max_length=80, blank=True)
    event_type = models.CharField(max_length=80, blank=True)
    event_date = models.DateField()
    event_start_datetime = models.DateTimeField(null=True, blank=True)
    event_end_datetime = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default="Africa/Johannesburg")
    venue_name_snapshot = models.CharField(max_length=180, blank=True)
    city_snapshot = models.CharField(max_length=120, blank=True)
    country_snapshot = models.CharField(max_length=100, blank=True)
    promoter_name_snapshot = models.CharField(max_length=180, blank=True)
    currency = models.CharField(
        max_length=3,
        default="ZAR",
        validators=[RegexValidator(r"^[A-Z]{3}$", "Use a three-letter uppercase currency code.")],
    )
    performance_fee = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    deposit_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    deposit_due_date = models.DateField(null=True, blank=True)
    balance_due_date = models.DateField(null=True, blank=True)
    internal_notes = models.TextField(blank=True, max_length=10000)
    custom_fields = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="bookings_created",
    )

    class Meta:
        ordering = ("event_date", "title")
        indexes = [
            models.Index(fields=("organization", "event_date")),
            models.Index(fields=("organization", "status", "priority")),
        ]

    def clean(self):
        relationships = (
            ("artist", self.artist),
            ("promoter", self.promoter),
            ("venue", self.venue),
        )
        for label, related in relationships:
            if related and related.organization_id != self.organization_id:
                raise ValidationError(
                    {label: f"Booking and {label} must belong to the same organization."}
                )
        if self.event_start_datetime and self.event_end_datetime:
            if self.event_end_datetime <= self.event_start_datetime:
                raise ValidationError(
                    {"event_end_datetime": "Event end must be after event start."}
                )

    def __str__(self):
        return f"{self.reference} - {self.title}"


class BookingStatusHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=20, choices=Booking.Status.choices)
    to_status = models.CharField(max_length=20, choices=Booking.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="booking_status_changes",
    )
    reason = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.booking.reference}: {self.from_status} to {self.to_status}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Booking status history is append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Booking status history cannot be deleted.")


class BookingTeamAssignment(TimestampedModel):
    class Responsibility(models.TextChoices):
        MANAGER = "manager", "Manager"
        BOOKING = "booking", "Booking"
        PRODUCTION = "production", "Production"
        FINANCE = "finance", "Finance"
        MARKETING = "marketing", "Marketing"
        GENERAL = "general", "General"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="team_assignments")
    membership = models.ForeignKey(
        "organizations.Membership",
        on_delete=models.PROTECT,
        related_name="booking_assignments",
    )
    responsibility = models.CharField(
        max_length=20, choices=Responsibility.choices, default=Responsibility.GENERAL
    )
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-is_primary", "responsibility", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("booking", "membership"), name="unique_booking_membership_assignment"
            ),
            models.UniqueConstraint(
                fields=("booking",),
                condition=Q(is_primary=True, is_active=True),
                name="one_active_primary_booking_assignment",
            ),
        ]

    def clean(self):
        if self.booking_id and self.membership_id:
            if self.booking.organization_id != self.membership.organization_id:
                raise ValidationError(
                    "Booking and membership must belong to the same organization."
                )
            if self.is_active and not (
                self.membership.is_active
                and self.membership.user.is_active
                and self.membership.organization.is_active
            ):
                raise ValidationError("Inactive memberships cannot be assigned to a booking.")
        if self.is_primary and not self.is_active:
            raise ValidationError("A primary booking assignment must be active.")


class BookingContactAssignment(TimestampedModel):
    class Responsibility(models.TextChoices):
        BOOKING = "booking", "Booking"
        PROMOTER = "promoter", "Promoter"
        VENUE = "venue", "Venue"
        PRODUCTION = "production", "Production"
        FINANCE = "finance", "Finance"
        HOSPITALITY = "hospitality", "Hospitality"
        GENERAL = "general", "General"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="contact_assignments"
    )
    contact = models.ForeignKey(
        "contacts.Contact", on_delete=models.PROTECT, related_name="booking_assignments"
    )
    responsibility = models.CharField(
        max_length=20, choices=Responsibility.choices, default=Responsibility.GENERAL
    )
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    snapshot_name = models.CharField(max_length=241)
    snapshot_email = models.EmailField(blank=True)
    snapshot_phone = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ("-is_primary", "responsibility", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("booking", "contact", "responsibility"),
                name="unique_booking_contact_responsibility",
            ),
            models.UniqueConstraint(
                fields=("booking", "responsibility"),
                condition=Q(is_primary=True, is_active=True),
                name="one_primary_booking_contact_per_role",
            ),
        ]

    def clean(self):
        if self.booking_id and self.contact_id:
            if self.booking.organization_id != self.contact.organization_id:
                raise ValidationError("Booking and contact must belong to the same organization.")
            if self.is_active and not self.contact.is_active:
                raise ValidationError("Inactive contacts cannot be assigned to a booking.")
        if self.is_primary and not self.is_active:
            raise ValidationError("A primary booking contact must be active.")


class BookingOption(TimestampedModel):
    class Category(models.TextChoices):
        PERFORMANCE = "performance", "Performance type"
        EVENT = "event", "Event type"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="booking_options")
    category = models.CharField(max_length=20, choices=Category.choices)
    name = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ("category", "name")
        constraints = [models.UniqueConstraint(fields=("organization", "category", "name"), name="unique_booking_option_name")]

    def __str__(self):
        return f"{self.category}: {self.name}"
