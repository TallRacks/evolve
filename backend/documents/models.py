import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel
from documents.template_validation import validate_template_text


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

    class SourceType(models.TextChoices):
        EXTERNAL = "external", "External reference"
        STORED = "stored", "Stored file"
        GENERATED = "generated", "Generated"

    class StorageStatus(models.TextChoices):
        NOT_APPLICABLE = "not_applicable", "Not applicable"
        AVAILABLE = "available", "Available"
        FAILED = "failed", "Failed"
        ARCHIVED = "archived", "Archived"

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
    source_type = models.CharField(
        max_length=20, choices=SourceType.choices, default=SourceType.EXTERNAL
    )
    storage_key = models.CharField(max_length=500, blank=True, editable=False)
    storage_provider = models.ForeignKey(
        "integrations.StorageProvider",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stored_documents",
    )
    external_url = models.URLField(max_length=1000, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=120, blank=True)
    detected_content_type = models.CharField(max_length=120, blank=True, editable=False)
    file_size = models.PositiveBigIntegerField(null=True, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True, editable=False)
    rendered_content = models.TextField(blank=True, editable=False)
    template = models.ForeignKey(
        "DocumentTemplate",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="generated_documents",
    )
    template_version = models.PositiveIntegerField(null=True, blank=True, editable=False)
    version_number = models.PositiveIntegerField(default=1)
    parent_document = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="newer_versions"
    )
    visibility = models.CharField(
        max_length=20, choices=Visibility.choices, default=Visibility.ORGANIZATION
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    storage_status = models.CharField(
        max_length=20, choices=StorageStatus.choices, default=StorageStatus.NOT_APPLICABLE
    )
    uploaded_at = models.DateTimeField(null=True, blank=True, editable=False)
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
        if self.rendered_content and self.source_type == self.SourceType.EXTERNAL:
            self.source_type = self.SourceType.GENERATED
        if self.source_type == self.SourceType.EXTERNAL:
            if not self.external_url:
                raise ValidationError({"external_url": "An HTTPS external reference is required."})
            if self.rendered_content or self.storage_key or self.storage_provider_id:
                raise ValidationError(
                    "External Documents cannot contain generated or stored content."
                )
            if not self.external_url.lower().startswith("https://"):
                raise ValidationError(
                    {"external_url": "Only HTTPS external references are supported."}
                )
        elif self.source_type == self.SourceType.GENERATED:
            if not self.rendered_content or self.external_url or self.storage_key:
                raise ValidationError("Generated Documents require rendered content only.")
        elif self.source_type == self.SourceType.STORED:
            required = {
                "storage_provider": self.storage_provider_id,
                "storage_key": self.storage_key,
                "checksum_sha256": self.checksum_sha256,
                "detected_content_type": self.detected_content_type,
            }
            missing = [field for field, value in required.items() if not value]
            if missing or self.file_size is None:
                errors = {field: "Required for stored files." for field in missing}
                if self.file_size is None:
                    errors["file_size"] = "Required for stored files."
                raise ValidationError(errors)
            if self.external_url or self.rendered_content:
                raise ValidationError(
                    "Stored Documents cannot contain external or generated content."
                )
            if self.storage_status not in {
                self.StorageStatus.AVAILABLE,
                self.StorageStatus.ARCHIVED,
            }:
                raise ValidationError(
                    {"storage_status": "Stored file must be available or archived."}
                )
        else:
            raise ValidationError({"source_type": "Unsupported Document source."})
        if self.source_type != self.SourceType.STORED and (
            self.storage_provider_id or self.storage_key or self.checksum_sha256
        ):
            raise ValidationError("Only stored Documents may reference binary storage.")
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


class DocumentTemplate(TimestampedModel):
    class Type(models.TextChoices):
        BOOKING_CONFIRMATION = "booking_confirmation", "Booking confirmation"
        CONTRACT_SUMMARY = "contract_summary", "Contract summary"
        INVOICE_COVER = "invoice_cover", "Invoice cover"
        TRAVEL_ITINERARY = "travel_itinerary", "Travel itinerary"
        PRODUCTION_ADVANCE = "production_advance", "Production advance"
        GENERAL = "general", "General"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="document_templates",
    )
    name = models.CharField(max_length=220)
    key = models.SlugField(max_length=120)
    document_type = models.CharField(max_length=32, choices=Type.choices)
    description = models.TextField(blank=True, max_length=2000)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="document_templates_created",
    )

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "key"), name="unique_document_template_key_per_organization"
            ),
            models.UniqueConstraint(
                fields=("key",),
                condition=Q(organization__isnull=True),
                name="unique_platform_document_template_key",
            ),
        ]

    def delete(self, *args, **kwargs):
        raise ValidationError("Templates cannot be deleted; deactivate them instead.")

    def __str__(self):
        return self.name


class DocumentTemplateSection(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        DocumentTemplate, on_delete=models.PROTECT, related_name="sections"
    )
    key = models.SlugField(max_length=120)
    title = models.CharField(max_length=220)
    body = models.TextField(max_length=10000)
    sequence = models.PositiveIntegerField(default=1)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ("sequence", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("template", "key"), name="unique_section_key_per_template"
            ),
            models.UniqueConstraint(
                fields=("template", "sequence"), name="unique_section_sequence_per_template"
            ),
        ]

    def clean(self):
        validate_template_text(self.title)
        validate_template_text(self.body)

    def delete(self, *args, **kwargs):
        raise ValidationError("Template sections are disabled rather than deleted.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.template}: {self.title}"


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
