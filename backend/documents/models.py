import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel


class Document(TimestampedModel):
    class Type(models.TextChoices):
        CONTRACT = "contract", "Contract"
        CALL_SHEET = "call_sheet", "Call sheet"
        RIDER = "rider", "Rider"
        PRESS = "press", "Press"
        ARTWORK = "artwork", "Artwork"
        MUSIC = "music", "Music"
        INVOICE = "invoice", "Invoice"
        RECEIPT = "receipt", "Receipt"
        TRAVEL = "travel", "Travel"
        OTHER = "other", "Other"

    class Visibility(models.TextChoices):
        ORGANIZATION = "organization", "Organization"
        RESTRICTED = "restricted", "Restricted"
        ARTIST = "artist", "Artist"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="documents"
    )
    title = models.CharField(max_length=220)
    document_type = models.CharField(max_length=24, choices=Type.choices)
    description = models.TextField(blank=True, max_length=5000)
    storage_key = models.CharField(max_length=500, blank=True, editable=False)
    external_url = models.URLField(max_length=1000, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=120, blank=True)
    file_size = models.PositiveBigIntegerField(null=True, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True, editable=False)
    version_number = models.PositiveIntegerField(default=1)
    parent_document = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="newer_versions"
    )
    visibility = models.CharField(
        max_length=20, choices=Visibility.choices, default=Visibility.ORGANIZATION
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="documents_uploaded",
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-updated_at", "title")
        constraints = [
            models.UniqueConstraint(
                fields=("parent_document", "version_number"),
                condition=Q(parent_document__isnull=False),
                name="unique_document_lineage_version",
            )
        ]
        indexes = [models.Index(fields=("organization", "status", "document_type"))]

    def clean(self):
        if self.storage_key:
            raise ValidationError({"storage_key": "Binary storage is not configured."})
        if not self.external_url:
            raise ValidationError({"external_url": "An HTTPS external reference is required."})
        if self.external_url and not self.external_url.lower().startswith("https://"):
            raise ValidationError({"external_url": "Only HTTPS external references are supported."})
        if self.parent_document_id:
            if self.parent_document.organization_id != self.organization_id:
                raise ValidationError("Document versions must remain in one organization.")
            if self.version_number <= self.parent_document.version_number:
                raise ValidationError({"version_number": "Version number must increase."})

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if old and old != self.status:
                raise ValidationError("Use the Document archive service.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Documents cannot be deleted; archive metadata instead.")


class DocumentLink(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="links")
    artist = models.ForeignKey(
        "artists.Artist",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="document_links",
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="document_links",
    )
    call_sheet = models.ForeignKey(
        "callsheets.CallSheet",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="document_links",
    )
    release = models.ForeignKey(
        "music.Release",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="document_links",
    )
    campaign = models.ForeignKey(
        "campaigns.Campaign",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="document_links",
    )
    travel_itinerary = models.ForeignKey(
        "travel.TravelItinerary",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="document_links",
    )
    travel_segment = models.ForeignKey(
        "travel.TravelSegment",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="document_links",
    )
    accommodation_stay = models.ForeignKey(
        "travel.AccommodationStay",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="document_links",
    )
    production_advance = models.ForeignKey(
        "production.ProductionAdvance",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="document_links",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        Q(artist__isnull=False)
                        & Q(booking__isnull=True)
                        & Q(call_sheet__isnull=True)
                        & Q(release__isnull=True)
                        & Q(campaign__isnull=True)
                        & Q(travel_itinerary__isnull=True)
                        & Q(travel_segment__isnull=True)
                        & Q(accommodation_stay__isnull=True)
                        & Q(production_advance__isnull=True)
                    )
                    | (
                        Q(artist__isnull=True)
                        & Q(booking__isnull=False)
                        & Q(call_sheet__isnull=True)
                        & Q(release__isnull=True)
                        & Q(campaign__isnull=True)
                        & Q(travel_itinerary__isnull=True)
                        & Q(travel_segment__isnull=True)
                        & Q(accommodation_stay__isnull=True)
                        & Q(production_advance__isnull=True)
                    )
                    | (
                        Q(artist__isnull=True)
                        & Q(booking__isnull=True)
                        & Q(call_sheet__isnull=False)
                        & Q(release__isnull=True)
                        & Q(campaign__isnull=True)
                        & Q(travel_itinerary__isnull=True)
                        & Q(travel_segment__isnull=True)
                        & Q(accommodation_stay__isnull=True)
                        & Q(production_advance__isnull=True)
                    )
                    | (
                        Q(artist__isnull=True)
                        & Q(booking__isnull=True)
                        & Q(call_sheet__isnull=True)
                        & Q(release__isnull=False)
                        & Q(campaign__isnull=True)
                        & Q(travel_itinerary__isnull=True)
                        & Q(travel_segment__isnull=True)
                        & Q(accommodation_stay__isnull=True)
                        & Q(production_advance__isnull=True)
                    )
                    | (
                        Q(artist__isnull=True)
                        & Q(booking__isnull=True)
                        & Q(call_sheet__isnull=True)
                        & Q(release__isnull=True)
                        & Q(campaign__isnull=False)
                        & Q(travel_itinerary__isnull=True)
                        & Q(travel_segment__isnull=True)
                        & Q(accommodation_stay__isnull=True)
                        & Q(production_advance__isnull=True)
                    )
                    | (
                        Q(artist__isnull=True)
                        & Q(booking__isnull=True)
                        & Q(call_sheet__isnull=True)
                        & Q(release__isnull=True)
                        & Q(campaign__isnull=True)
                        & Q(travel_itinerary__isnull=False)
                        & Q(travel_segment__isnull=True)
                        & Q(accommodation_stay__isnull=True)
                        & Q(production_advance__isnull=True)
                    )
                    | (
                        Q(artist__isnull=True)
                        & Q(booking__isnull=True)
                        & Q(call_sheet__isnull=True)
                        & Q(release__isnull=True)
                        & Q(campaign__isnull=True)
                        & Q(travel_itinerary__isnull=True)
                        & Q(travel_segment__isnull=False)
                        & Q(accommodation_stay__isnull=True)
                        & Q(production_advance__isnull=True)
                    )
                    | (
                        Q(artist__isnull=True)
                        & Q(booking__isnull=True)
                        & Q(call_sheet__isnull=True)
                        & Q(release__isnull=True)
                        & Q(campaign__isnull=True)
                        & Q(travel_itinerary__isnull=True)
                        & Q(travel_segment__isnull=True)
                        & Q(accommodation_stay__isnull=False)
                        & Q(production_advance__isnull=True)
                    )
                    | (
                        Q(artist__isnull=True)
                        & Q(booking__isnull=True)
                        & Q(call_sheet__isnull=True)
                        & Q(release__isnull=True)
                        & Q(campaign__isnull=True)
                        & Q(travel_itinerary__isnull=True)
                        & Q(travel_segment__isnull=True)
                        & Q(accommodation_stay__isnull=True)
                        & Q(production_advance__isnull=False)
                    )
                ),
                name="document_link_exactly_one_entity",
            ),
            models.UniqueConstraint(
                fields=("document", "artist"),
                condition=Q(artist__isnull=False),
                name="unique_document_artist_link",
            ),
            models.UniqueConstraint(
                fields=("document", "booking"),
                condition=Q(booking__isnull=False),
                name="unique_document_booking_link",
            ),
            models.UniqueConstraint(
                fields=("document", "call_sheet"),
                condition=Q(call_sheet__isnull=False),
                name="unique_document_call_sheet_link",
            ),
            models.UniqueConstraint(
                fields=("document", "release"),
                condition=Q(release__isnull=False),
                name="unique_document_release_link",
            ),
            models.UniqueConstraint(
                fields=("document", "campaign"),
                condition=Q(campaign__isnull=False),
                name="unique_document_campaign_link",
            ),
            models.UniqueConstraint(
                fields=("document", "travel_itinerary"),
                condition=Q(travel_itinerary__isnull=False),
                name="unique_document_travel_itinerary_link",
            ),
            models.UniqueConstraint(
                fields=("document", "travel_segment"),
                condition=Q(travel_segment__isnull=False),
                name="unique_document_travel_segment_link",
            ),
            models.UniqueConstraint(
                fields=("document", "accommodation_stay"),
                condition=Q(accommodation_stay__isnull=False),
                name="unique_document_accommodation_stay_link",
            ),
            models.UniqueConstraint(
                fields=("document", "production_advance"),
                condition=Q(production_advance__isnull=False),
                name="unique_document_production_advance_link",
            ),
        ]

    @property
    def entity(self):
        return next(
            value
            for value in (
                self.artist,
                self.booking,
                self.call_sheet,
                self.release,
                self.campaign,
                self.travel_itinerary,
                self.travel_segment,
                self.accommodation_stay,
                self.production_advance,
                self.production_advance,
            )
            if value
        )

    @property
    def entity_type(self):
        return next(
            name
            for name in (
                "artist",
                "booking",
                "call_sheet",
                "release",
                "campaign",
                "travel_itinerary",
                "travel_segment",
                "accommodation_stay",
                "production_advance",
            )
            if getattr(self, f"{name}_id")
        )

    def clean(self):
        entities = [
            self.artist,
            self.booking,
            self.call_sheet,
            self.release,
            self.campaign,
            self.travel_itinerary,
            self.travel_segment,
            self.accommodation_stay,
            self.production_advance,
        ]
        selected = [entity for entity in entities if entity]
        if len(selected) != 1:
            raise ValidationError("A document link must select exactly one entity.")
        organization_id = getattr(selected[0], "organization_id", None)
        if organization_id is None:
            organization_id = selected[0].itinerary.organization_id
        if organization_id != self.document.organization_id:
            raise ValidationError(
                "Document and linked entity must belong to the same organization."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Unlink documents through the document service.")
