import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel


class CallSheet(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="call_sheets"
    )
    booking = models.OneToOneField(
        "bookings.Booking", on_delete=models.PROTECT, related_name="call_sheet"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="call_sheets_created",
    )

    class Meta:
        ordering = ("-booking__event_date",)

    def clean(self):
        if self.booking_id and self.organization_id != self.booking.organization_id:
            raise ValidationError("Call Sheet and Booking must belong to the same organization.")

    def __str__(self):
        return f"Call Sheet {self.booking.reference}"

    def delete(self, *args, **kwargs):
        raise ValidationError("Call Sheets cannot be deleted.")


class CallSheetVersion(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        PUBLISHED = "published", "Published"
        SUPERSEDED = "superseded", "Superseded"
        CANCELLED = "cancelled", "Cancelled"

    IMMUTABLE_STATUSES = {Status.PUBLISHED, Status.SUPERSEDED, Status.CANCELLED}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    call_sheet = models.ForeignKey(CallSheet, on_delete=models.PROTECT, related_name="versions")
    version_number = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="call_sheet_versions_created",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="call_sheet_versions_published",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    title = models.CharField(max_length=220)
    subtitle = models.CharField(max_length=220, blank=True)
    event_name = models.CharField(max_length=220)
    artist_name = models.CharField(max_length=220)
    event_date = models.DateField()
    event_start_datetime = models.DateTimeField(null=True, blank=True)
    event_end_datetime = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64)
    venue_name = models.CharField(max_length=180, blank=True)
    venue_address = models.CharField(max_length=520, blank=True)
    city = models.CharField(max_length=120, blank=True)
    province = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=100, blank=True)
    venue_phone = models.CharField(max_length=40, blank=True)
    promoter_name = models.CharField(max_length=180, blank=True)
    access_notes = models.TextField(blank=True, max_length=5000)
    loading_access = models.TextField(blank=True, max_length=5000)
    parking_notes = models.TextField(blank=True, max_length=5000)
    backstage_access = models.TextField(blank=True, max_length=5000)
    dressing_room_notes = models.TextField(blank=True, max_length=5000)
    emergency_procedure_notes = models.TextField(blank=True, max_length=5000)
    soundcheck_time = models.TimeField(null=True, blank=True)
    production_contact = models.CharField(max_length=220, blank=True)
    stage_notes = models.TextField(blank=True, max_length=5000)
    technical_notes = models.TextField(blank=True, max_length=5000)
    backline_notes = models.TextField(blank=True, max_length=5000)
    special_requirements = models.TextField(blank=True, max_length=5000)
    catering_notes = models.TextField(blank=True, max_length=5000)
    dietary_notes = models.TextField(blank=True, max_length=5000)
    guest_notes = models.TextField(blank=True, max_length=5000)
    general_notes = models.TextField(blank=True, max_length=10000)
    artist_notes = models.TextField(blank=True, max_length=5000)
    team_notes = models.TextField(blank=True, max_length=5000)
    security_notes = models.TextField(blank=True, max_length=5000)
    emergency_notes = models.TextField(blank=True, max_length=5000)

    class Meta:
        ordering = ("-version_number",)
        constraints = [
            models.UniqueConstraint(
                fields=("call_sheet", "version_number"), name="unique_call_sheet_version_number"
            ),
            models.UniqueConstraint(
                fields=("call_sheet",),
                condition=Q(status="published"),
                name="one_published_version_per_call_sheet",
            ),
        ]

    @property
    def is_editable(self):
        return self.status in {self.Status.DRAFT, self.Status.READY}

    def save(self, *args, **kwargs):
        if self.pk:
            previous = (
                type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )
            if previous in self.IMMUTABLE_STATUSES:
                raise ValidationError(
                    "Published, superseded, and cancelled versions are immutable."
                )
            if previous and previous != self.status:
                raise ValidationError("Use a Call Sheet lifecycle service to change status.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Call Sheet versions cannot be deleted.")

    def __str__(self):
        return f"{self.call_sheet.booking.reference} v{self.version_number}"


class VersionChild(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(CallSheetVersion, on_delete=models.PROTECT)
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True
        ordering = ("sequence", "created_at")

    def clean(self):
        if self.version_id:
            status = (
                CallSheetVersion.objects.filter(pk=self.version_id)
                .values_list("status", flat=True)
                .first()
            )
            if status not in {CallSheetVersion.Status.DRAFT, CallSheetVersion.Status.READY}:
                raise ValidationError("Entries on this Call Sheet version are immutable.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        status = (
            CallSheetVersion.objects.filter(pk=self.version_id)
            .values_list("status", flat=True)
            .first()
        )
        if status not in {CallSheetVersion.Status.DRAFT, CallSheetVersion.Status.READY}:
            raise ValidationError("Entries on this Call Sheet version are immutable.")
        super().delete(*args, **kwargs)


class CallSheetScheduleItem(VersionChild):
    version = models.ForeignKey(
        CallSheetVersion, on_delete=models.PROTECT, related_name="schedule_items"
    )
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, max_length=3000)
    location = models.CharField(max_length=220, blank=True)
    responsibility = models.CharField(max_length=220, blank=True)
    is_highlighted = models.BooleanField(default=False)


class CallSheetTeamEntry(VersionChild):
    version = models.ForeignKey(
        CallSheetVersion, on_delete=models.PROTECT, related_name="team_entries"
    )
    booking_team_assignment = models.ForeignKey(
        "bookings.BookingTeamAssignment", null=True, blank=True, on_delete=models.SET_NULL
    )
    membership = models.ForeignKey(
        "organizations.Membership", null=True, blank=True, on_delete=models.SET_NULL
    )
    name_snapshot = models.CharField(max_length=301)
    role_snapshot = models.CharField(max_length=120, blank=True)
    responsibility_snapshot = models.CharField(max_length=220, blank=True)
    phone_snapshot = models.CharField(max_length=40, blank=True)
    email_snapshot = models.EmailField(blank=True)
    call_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True, max_length=3000)

    def clean(self):
        super().clean()
        organization_id = self.version.call_sheet.organization_id
        if self.membership_id and self.membership.organization_id != organization_id:
            raise ValidationError("Team membership must belong to the Call Sheet organization.")
        if (
            self.booking_team_assignment_id
            and self.booking_team_assignment.booking_id != self.version.call_sheet.booking_id
        ):
            raise ValidationError("Booking team assignment must belong to the Call Sheet Booking.")


class CallSheetContactEntry(VersionChild):
    version = models.ForeignKey(
        CallSheetVersion, on_delete=models.PROTECT, related_name="contact_entries"
    )
    source_contact = models.ForeignKey(
        "contacts.Contact", null=True, blank=True, on_delete=models.SET_NULL
    )
    responsibility = models.CharField(max_length=220)
    name_snapshot = models.CharField(max_length=241)
    company_snapshot = models.CharField(max_length=220, blank=True)
    email_snapshot = models.EmailField(blank=True)
    phone_snapshot = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True, max_length=3000)
    is_primary = models.BooleanField(default=False)

    def clean(self):
        super().clean()
        if (
            self.source_contact_id
            and self.source_contact.organization_id != self.version.call_sheet.organization_id
        ):
            raise ValidationError("Contact must belong to the Call Sheet organization.")


class CallSheetTravelItem(VersionChild):
    class Type(models.TextChoices):
        FLIGHT = "flight", "Flight"
        GROUND = "ground", "Ground"
        TRAIN = "train", "Train"
        OTHER = "other", "Other"

    version = models.ForeignKey(
        CallSheetVersion, on_delete=models.PROTECT, related_name="travel_items"
    )
    type = models.CharField(max_length=16, choices=Type.choices)
    provider = models.CharField(max_length=220, blank=True)
    reference = models.CharField(max_length=220, blank=True)
    departure_location = models.CharField(max_length=220)
    arrival_location = models.CharField(max_length=220)
    departure_datetime = models.DateTimeField()
    arrival_datetime = models.DateTimeField(null=True, blank=True)
    traveler_notes = models.TextField(blank=True, max_length=3000)
    contact_name = models.CharField(max_length=220, blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True, max_length=3000)

    def clean(self):
        super().clean()
        if self.arrival_datetime and self.arrival_datetime <= self.departure_datetime:
            raise ValidationError("Travel arrival must be after departure.")


class CallSheetAccommodationItem(VersionChild):
    version = models.ForeignKey(
        CallSheetVersion, on_delete=models.PROTECT, related_name="accommodation_items"
    )
    property_name = models.CharField(max_length=220)
    address = models.CharField(max_length=520, blank=True)
    check_in_datetime = models.DateTimeField()
    check_out_datetime = models.DateTimeField(null=True, blank=True)
    confirmation_reference = models.CharField(max_length=220, blank=True)
    contact_name = models.CharField(max_length=220, blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True, max_length=3000)

    def clean(self):
        super().clean()
        if self.check_out_datetime and self.check_out_datetime <= self.check_in_datetime:
            raise ValidationError("Accommodation check-out must be after check-in.")
