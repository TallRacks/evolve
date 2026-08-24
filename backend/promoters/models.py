import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel


class Promoter(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="promoters"
    )
    name = models.CharField(max_length=180)
    company_name = models.CharField(max_length=180, blank=True)
    slug = models.SlugField(max_length=120)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    website = models.URLField(max_length=500, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    province = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=30, blank=True)
    country = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True, max_length=5000)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "slug"), name="unique_promoter_slug_per_organization"
            )
        ]
        indexes = [models.Index(fields=("organization", "status"))]

    def __str__(self):
        return self.name


class PromoterContact(TimestampedModel):
    class Responsibility(models.TextChoices):
        PROMOTER = "promoter", "Promoter"
        PRODUCTION = "production", "Production"
        FINANCE = "finance", "Finance"
        HOSPITALITY = "hospitality", "Hospitality"
        MARKETING = "marketing", "Marketing"
        GENERAL = "general", "General"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promoter = models.ForeignKey(Promoter, on_delete=models.CASCADE, related_name="contact_links")
    contact = models.ForeignKey(
        "contacts.Contact", on_delete=models.PROTECT, related_name="promoter_links"
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
                fields=("promoter", "contact"), name="unique_promoter_contact_link"
            ),
            models.UniqueConstraint(
                fields=("promoter", "responsibility"),
                condition=Q(is_primary=True, is_active=True),
                name="one_primary_promoter_contact_per_role",
            ),
        ]

    def clean(self):
        if self.promoter_id and self.contact_id:
            if self.promoter.organization_id != self.contact.organization_id:
                raise ValidationError("Promoter and contact must belong to the same organization.")
            if self.is_active and not self.contact.is_active:
                raise ValidationError("Inactive contacts cannot be linked to a promoter.")
        if self.is_primary and not self.is_active:
            raise ValidationError("A primary contact relationship must be active.")

    def __str__(self):
        return f"{self.promoter} - {self.contact}"
