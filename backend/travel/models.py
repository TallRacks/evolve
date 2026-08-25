import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as error:
        raise ValidationError("Use a valid IANA timezone identifier.") from error


class TravelItinerary(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONFIRMED = "confirmed", "Confirmed"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="travel_itineraries"
    )
    artist = models.ForeignKey(
        "artists.Artist", on_delete=models.PROTECT, related_name="travel_itineraries"
    )
    booking = models.OneToOneField(
        "bookings.Booking",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="travel_itinerary",
    )
    title = models.CharField(max_length=220)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(
        max_length=64, default="Africa/Johannesburg", validators=[validate_timezone]
    )
    purpose = models.CharField(max_length=500, blank=True)
    notes = models.TextField(max_length=5000, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="travel_itineraries_created",
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("starts_at", "title")
        indexes = [models.Index(fields=("organization", "status", "starts_at"))]

    def clean(self):
        if self.pk:
            previous = (
                type(self).objects.filter(pk=self.pk).values("organization_id", "artist_id").first()
            )
            parent_changed = previous and (
                previous["organization_id"] != self.organization_id
                or previous["artist_id"] != self.artist_id
            )
            if parent_changed and (
                self.travellers.exists() or self.segments.exists() or self.stays.exists()
            ):
                raise ValidationError(
                    "Organization and Artist cannot change after itinerary children exist."
                )
        if (
            self.artist_id
            and self.organization_id
            and self.artist.organization_id != self.organization_id
        ):
            raise ValidationError(
                {"artist": "Artist and itinerary must belong to the same organization."}
            )
        if self.booking_id:
            if self.booking.organization_id != self.organization_id:
                raise ValidationError(
                    {"booking": "Booking and itinerary must belong to the same organization."}
                )
            if self.booking.artist_id != self.artist_id:
                raise ValidationError(
                    {"booking": "Booking and itinerary must use the same Artist."}
                )
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "End must be after start."})

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if old and old != self.status:
                raise ValidationError("Use the itinerary lifecycle service to change status.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Itineraries cannot be deleted; archive them instead.")

    def __str__(self):
        return self.title


class ItineraryTraveller(TimestampedModel):
    class Type(models.TextChoices):
        ARTIST = "artist", "Artist"
        TEAM = "team", "Team"
        GUEST = "guest", "Guest"
        CREW = "crew", "Crew"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    itinerary = models.ForeignKey(
        TravelItinerary, on_delete=models.PROTECT, related_name="travellers"
    )
    artist = models.ForeignKey(
        "artists.Artist",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="itinerary_traveller_entries",
    )
    membership = models.ForeignKey(
        "organizations.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="itinerary_traveller_entries",
    )
    display_name = models.CharField(max_length=301, blank=True)
    traveller_type = models.CharField(max_length=20, choices=Type.choices)
    email_snapshot = models.EmailField(blank=True)
    phone_snapshot = models.CharField(max_length=40, blank=True)
    notes = models.TextField(max_length=3000, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("traveller_type", "display_name")
        constraints = [
            models.CheckConstraint(
                condition=Q(artist__isnull=False)
                | Q(membership__isnull=False)
                | ~Q(display_name=""),
                name="travel_traveller_has_identity",
            )
        ]

    def clean(self):
        if self.pk:
            previous_itinerary = (
                type(self).objects.filter(pk=self.pk).values_list("itinerary_id", flat=True).first()
            )
            if previous_itinerary != self.itinerary_id and (
                self.segment_assignments.exists() or self.room_assignments.exists()
            ):
                raise ValidationError("Assigned travellers cannot move to another itinerary.")
        if not (self.artist_id or self.membership_id or self.display_name.strip()):
            raise ValidationError("A traveller requires an Artist, membership, or display name.")
        if self.artist_id and self.artist.organization_id != self.itinerary.organization_id:
            raise ValidationError(
                {"artist": "Traveller Artist must belong to the itinerary organization."}
            )
        if self.membership_id:
            if self.membership.organization_id != self.itinerary.organization_id:
                raise ValidationError(
                    {
                        "membership": (
                            "Traveller membership must belong to the itinerary organization."
                        )
                    }
                )
            if self.is_active and not (
                self.membership.is_active
                and self.membership.user.is_active
                and self.membership.organization.is_active
            ):
                raise ValidationError(
                    {"membership": "Only an access-valid membership can be assigned."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name or str(self.artist or self.membership)


class TravelSegment(TimestampedModel):
    class Type(models.TextChoices):
        FLIGHT = "flight", "Flight"
        RAIL = "rail", "Rail"
        GROUND = "ground", "Ground"
        FERRY = "ferry", "Ferry"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    itinerary = models.ForeignKey(
        TravelItinerary, on_delete=models.PROTECT, related_name="segments"
    )
    segment_type = models.CharField(max_length=20, choices=Type.choices)
    sequence = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    provider = models.CharField(max_length=220, blank=True)
    service_number = models.CharField(max_length=80, blank=True)
    confirmation_reference = models.CharField(max_length=220, blank=True)
    departure_location = models.CharField(max_length=220)
    arrival_location = models.CharField(max_length=220)
    departure_at = models.DateTimeField()
    arrival_at = models.DateTimeField(null=True, blank=True)
    departure_timezone = models.CharField(max_length=64, validators=[validate_timezone])
    arrival_timezone = models.CharField(max_length=64, validators=[validate_timezone])
    terminal_or_platform = models.CharField(max_length=120, blank=True)
    seat_or_vehicle_info = models.CharField(max_length=220, blank=True)
    airline = models.CharField(max_length=180, blank=True)
    flight_number = models.CharField(max_length=40, blank=True)
    departure_airport_code = models.CharField(
        max_length=3,
        blank=True,
        validators=[RegexValidator(r"^[A-Z]{3}$", "Use a three-letter uppercase airport code.")],
    )
    arrival_airport_code = models.CharField(
        max_length=3,
        blank=True,
        validators=[RegexValidator(r"^[A-Z]{3}$", "Use a three-letter uppercase airport code.")],
    )
    driver_name = models.CharField(max_length=220, blank=True)
    driver_phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(max_length=3000, blank=True)

    class Meta:
        ordering = ("sequence", "departure_at")
        constraints = [
            models.UniqueConstraint(
                fields=("itinerary", "sequence"), name="unique_travel_segment_sequence"
            )
        ]
        indexes = [models.Index(fields=("itinerary", "departure_at"))]

    def clean(self):
        if self.pk:
            previous_itinerary = (
                type(self).objects.filter(pk=self.pk).values_list("itinerary_id", flat=True).first()
            )
            if previous_itinerary != self.itinerary_id and self.traveller_assignments.exists():
                raise ValidationError("Assigned segments cannot move to another itinerary.")
        if self.arrival_at and self.arrival_at <= self.departure_at:
            raise ValidationError({"arrival_at": "Arrival must be after departure."})
        if self.segment_type == self.Type.FLIGHT and (
            not self.departure_airport_code or not self.arrival_airport_code
        ):
            raise ValidationError("Flights require departure and arrival airport codes.")

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if old and old != self.status:
                raise ValidationError("Use the segment lifecycle service to change status.")
        self.full_clean()
        super().save(*args, **kwargs)


class TravelSegmentTraveller(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    segment = models.ForeignKey(
        TravelSegment, on_delete=models.CASCADE, related_name="traveller_assignments"
    )
    traveller = models.ForeignKey(
        ItineraryTraveller, on_delete=models.PROTECT, related_name="segment_assignments"
    )
    seat = models.CharField(max_length=80, blank=True)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("segment", "traveller"), name="unique_segment_traveller"
            )
        ]

    def __str__(self):
        return f"{self.segment} / {self.traveller}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if (
            self.segment_id
            and self.traveller_id
            and self.segment.itinerary_id != self.traveller.itinerary_id
        ):
            raise ValidationError("Segment and traveller must belong to the same itinerary.")


class AccommodationStay(TimestampedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        CONFIRMED = "confirmed", "Confirmed"
        CHECKED_IN = "checked_in", "Checked in"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    itinerary = models.ForeignKey(TravelItinerary, on_delete=models.PROTECT, related_name="stays")
    property_name = models.CharField(max_length=220)
    address = models.CharField(max_length=520, blank=True)
    city = models.CharField(max_length=120)
    country = models.CharField(max_length=100)
    timezone = models.CharField(max_length=64, validators=[validate_timezone])
    check_in_at = models.DateTimeField()
    check_out_at = models.DateTimeField()
    confirmation_reference = models.CharField(max_length=220, blank=True)
    contact_name = models.CharField(max_length=220, blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    contact_email = models.EmailField(blank=True)
    notes = models.TextField(max_length=3000, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("sequence", "check_in_at")
        constraints = [
            models.UniqueConstraint(
                fields=("itinerary", "sequence"), name="unique_accommodation_sequence"
            )
        ]

    def clean(self):
        if self.pk:
            previous_itinerary = (
                type(self).objects.filter(pk=self.pk).values_list("itinerary_id", flat=True).first()
            )
            if previous_itinerary != self.itinerary_id and self.room_assignments.exists():
                raise ValidationError("Accommodation with rooms cannot move to another itinerary.")
        if self.check_out_at <= self.check_in_at:
            raise ValidationError({"check_out_at": "Check-out must be after check-in."})

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if old and old != self.status:
                raise ValidationError("Use the accommodation lifecycle service to change status.")
        self.full_clean()
        super().save(*args, **kwargs)


class AccommodationRoomAssignment(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stay = models.ForeignKey(
        AccommodationStay, on_delete=models.CASCADE, related_name="room_assignments"
    )
    traveller = models.ForeignKey(
        ItineraryTraveller, on_delete=models.PROTECT, related_name="room_assignments"
    )
    room_label = models.CharField(max_length=120, blank=True)
    room_type = models.CharField(max_length=120, blank=True)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("stay", "traveller"), name="unique_stay_traveller_room")
        ]

    def clean(self):
        if (
            self.stay_id
            and self.traveller_id
            and self.stay.itinerary_id != self.traveller.itinerary_id
        ):
            raise ValidationError("Stay and traveller must belong to the same itinerary.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
