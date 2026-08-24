import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel


class Artist(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="artists"
    )
    stage_name = models.CharField(max_length=180)
    legal_name = models.CharField(max_length=180, blank=True)
    slug = models.SlugField(max_length=120)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    biography = models.TextField(blank=True, max_length=10000)
    website = models.URLField(max_length=500, blank=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=120, blank=True)
    management_email = models.EmailField(blank=True)
    booking_email = models.EmailField(blank=True)
    profile_image_url = models.URLField(max_length=500, blank=True)

    class Meta:
        ordering = ("stage_name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "slug"),
                name="unique_artist_slug_per_organization",
            )
        ]
        indexes = [models.Index(fields=("organization", "status"))]

    def __str__(self):
        return self.stage_name


class ArtistTeamAssignment(TimestampedModel):
    class Responsibility(models.TextChoices):
        MANAGER = "manager", "Manager"
        BOOKING = "booking", "Booking"
        MARKETING = "marketing", "Marketing"
        FINANCE = "finance", "Finance"
        GENERAL = "general", "General"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    artist = models.ForeignKey(
        Artist, on_delete=models.CASCADE, related_name="team_assignments"
    )
    membership = models.ForeignKey(
        "organizations.Membership",
        on_delete=models.PROTECT,
        related_name="artist_assignments",
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
                fields=("artist", "membership"),
                name="unique_artist_membership_assignment",
            ),
            models.UniqueConstraint(
                fields=("artist",),
                condition=Q(is_primary=True, is_active=True),
                name="one_active_primary_assignment_per_artist",
            ),
        ]

    def clean(self):
        if self.artist_id and self.membership_id:
            if self.artist.organization_id != self.membership.organization_id:
                raise ValidationError(
                    "Artist and membership must belong to the same organization."
                )
            if self.is_active and not (
                self.membership.is_active
                and self.membership.user.is_active
                and self.membership.organization.is_active
            ):
                raise ValidationError(
                    "Inactive memberships cannot be assigned to an artist."
                )
        if self.is_primary and not self.is_active:
            raise ValidationError("A primary assignment must be active.")

    def __str__(self):
        return f"{self.artist} - {self.membership.user}"


class ArtistPortalLink(TimestampedModel):
    class Relationship(models.TextChoices):
        ARTIST = "artist", "Artist"
        ASSISTANT = "assistant", "Assistant"
        CO_MANAGER = "co_manager", "Co-manager"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    artist = models.ForeignKey(
        Artist, on_delete=models.CASCADE, related_name="portal_links"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="artist_portal_links",
    )
    relationship = models.CharField(
        max_length=20, choices=Relationship.choices, default=Relationship.ARTIST
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("artist", "user"), name="unique_artist_portal_user_link"
            )
        ]

    def clean(self):
        if self.artist_id and self.user_id:
            from organizations.models import Membership

            if (
                not Membership.objects.active()
                .filter(
                    organization_id=self.artist.organization_id, user_id=self.user_id
                )
                .exists()
            ):
                raise ValidationError(
                    "Portal users require active membership in the artist organization."
                )

    def __str__(self):
        return f"{self.artist} - {self.user}"
