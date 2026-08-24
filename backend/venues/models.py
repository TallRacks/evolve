import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel


class Venue(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="venues"
    )
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=120)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    province = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=30, blank=True)
    country = models.CharField(max_length=100, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    website = models.URLField(max_length=500, blank=True)
    public_phone = models.CharField(max_length=40, blank=True)
    public_email = models.EmailField(blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    timezone = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "slug"), name="unique_venue_slug_per_organization"
            )
        ]
        indexes = [models.Index(fields=("organization", "status"))]

    def clean(self):
        if bool(self.latitude is None) != bool(self.longitude is None):
            raise ValidationError("Latitude and longitude must be provided together.")

    def __str__(self):
        return self.name


class VenueContact(TimestampedModel):
    class Responsibility(models.TextChoices):
        VENUE_MANAGER = "venue_manager", "Venue manager"
        PRODUCTION = "production", "Production"
        TECHNICAL = "technical", "Technical"
        HOSPITALITY = "hospitality", "Hospitality"
        SECURITY = "security", "Security"
        FINANCE = "finance", "Finance"
        GENERAL = "general", "General"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name="contact_links")
    contact = models.ForeignKey(
        "contacts.Contact", on_delete=models.PROTECT, related_name="venue_links"
    )
    responsibility = models.CharField(
        max_length=24, choices=Responsibility.choices, default=Responsibility.GENERAL
    )
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-is_primary", "responsibility", "created_at")
        constraints = [
            models.UniqueConstraint(fields=("venue", "contact"), name="unique_venue_contact_link"),
            models.UniqueConstraint(
                fields=("venue", "responsibility"),
                condition=Q(is_primary=True, is_active=True),
                name="one_primary_venue_contact_per_role",
            ),
        ]

    def clean(self):
        if self.venue_id and self.contact_id:
            if self.venue.organization_id != self.contact.organization_id:
                raise ValidationError("Venue and contact must belong to the same organization.")
            if self.is_active and not self.contact.is_active:
                raise ValidationError("Inactive contacts cannot be linked to a venue.")
        if self.is_primary and not self.is_active:
            raise ValidationError("A primary contact relationship must be active.")

    def __str__(self):
        return f"{self.venue} - {self.contact}"
