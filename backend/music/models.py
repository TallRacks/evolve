import re
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel

ISRC_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}\d{7}$")
UPC_PATTERN = re.compile(r"^\d{8,14}$")


class Release(TimestampedModel):
    class Type(models.TextChoices):
        SINGLE = "single", "Single"
        EP = "ep", "EP"
        ALBUM = "album", "Album"
        MIXTAPE = "mixtape", "Mixtape"
        COMPILATION = "compilation", "Compilation"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        RELEASED = "released", "Released"
        CANCELLED = "cancelled", "Cancelled"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="music_releases"
    )
    primary_artist = models.ForeignKey(
        "artists.Artist", on_delete=models.PROTECT, related_name="music_releases"
    )
    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=140)
    release_type = models.CharField(max_length=20, choices=Type.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    planned_release_date = models.DateField(null=True, blank=True)
    release_datetime = models.DateTimeField(null=True, blank=True)
    original_release_date = models.DateField(null=True, blank=True)
    upc_ean = models.CharField(max_length=14, blank=True)
    catalog_number = models.CharField(max_length=80, blank=True)
    artwork_url = models.URLField(max_length=500, blank=True)
    public_url = models.URLField(max_length=500, blank=True)
    presave_url = models.URLField(max_length=500, blank=True)
    label_name = models.CharField(max_length=180, blank=True)
    distributor_name = models.CharField(max_length=180, blank=True)
    internal_notes = models.TextField(blank=True, max_length=10000)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="music_releases_created",
    )

    class Meta:
        ordering = ("-planned_release_date", "title")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "slug"), name="unique_release_slug_per_organization"
            ),
            models.UniqueConstraint(
                fields=("upc_ean",),
                condition=~Q(upc_ean=""),
                name="unique_nonempty_release_upc",
            ),
        ]
        indexes = [models.Index(fields=("organization", "status", "planned_release_date"))]

    def clean(self):
        if self.primary_artist_id and self.primary_artist.organization_id != self.organization_id:
            raise ValidationError(
                "Release and primary artist must belong to the same organization."
            )
        if self.upc_ean and not UPC_PATTERN.fullmatch(self.upc_ean):
            raise ValidationError({"upc_ean": "UPC/EAN must contain 8 to 14 digits."})
        if self.status == self.Status.SCHEDULED and not self.planned_release_date:
            raise ValidationError({"planned_release_date": "Scheduled releases require a date."})

    def save(self, *args, **kwargs):
        self.upc_ean = self.upc_ean.strip()
        if self.pk:
            previous = (
                type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )
            if previous and previous != self.status:
                raise ValidationError("Use the Release lifecycle service to change status.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Releases cannot be deleted; archive them instead.")

    def __str__(self):
        return f"{self.primary_artist} - {self.title}"


class Track(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="music_tracks"
    )
    primary_artist = models.ForeignKey(
        "artists.Artist", on_delete=models.PROTECT, related_name="music_tracks"
    )
    title = models.CharField(max_length=220)
    version_title = models.CharField(max_length=120, blank=True)
    slug = models.SlugField(max_length=140)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    isrc = models.CharField(max_length=12, blank=True)
    internal_reference = models.CharField(max_length=80, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    explicit_content = models.BooleanField(default=False)
    artwork_url = models.URLField(max_length=500, blank=True)
    audio_preview_url = models.URLField(max_length=500, blank=True)
    release_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1900), MaxValueValidator(2200)],
    )
    language = models.CharField(max_length=80, blank=True)
    genre = models.CharField(max_length=100, blank=True)
    subgenre = models.CharField(max_length=100, blank=True)
    internal_notes = models.TextField(blank=True, max_length=10000)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="music_tracks_created",
    )

    class Meta:
        ordering = ("title", "version_title")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "slug"), name="unique_track_slug_per_organization"
            ),
            models.UniqueConstraint(
                fields=("isrc",), condition=~Q(isrc=""), name="unique_nonempty_track_isrc"
            ),
        ]
        indexes = [models.Index(fields=("organization", "primary_artist", "status"))]

    def clean(self):
        if self.primary_artist_id and self.primary_artist.organization_id != self.organization_id:
            raise ValidationError("Track and primary artist must belong to the same organization.")
        if self.isrc and not ISRC_PATTERN.fullmatch(self.isrc):
            raise ValidationError({"isrc": "ISRC must use the 12-character CCXXXYYNNNNN format."})

    def save(self, *args, **kwargs):
        self.isrc = self.isrc.replace("-", "").replace(" ", "").upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Tracks cannot be deleted; archive them instead.")

    def __str__(self):
        return f"{self.title} ({self.version_title})" if self.version_title else self.title


class ReleaseTrack(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    release = models.ForeignKey(Release, on_delete=models.PROTECT, related_name="track_placements")
    track = models.ForeignKey(Track, on_delete=models.PROTECT, related_name="release_placements")
    disc_number = models.PositiveSmallIntegerField(default=1)
    track_number = models.PositiveSmallIntegerField()
    sequence = models.PositiveIntegerField(default=1)
    is_focus_track = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sequence", "disc_number", "track_number")
        constraints = [
            models.UniqueConstraint(
                fields=("release", "track"), name="unique_track_placement_per_release"
            ),
            models.UniqueConstraint(
                fields=("release", "disc_number", "track_number"),
                name="unique_release_disc_track_number",
            ),
        ]

    def __str__(self):
        return f"{self.release} / {self.disc_number}.{self.track_number} {self.track}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.release_id and self.track_id:
            if self.release.organization_id != self.track.organization_id:
                raise ValidationError("Release and Track must belong to the same organization.")
            if self.release.primary_artist_id != self.track.primary_artist_id:
                raise ValidationError("Release and Track primary artists must match.")


class MusicCredit(TimestampedModel):
    class Role(models.TextChoices):
        PRIMARY_ARTIST = "primary_artist", "Primary artist"
        FEATURED_ARTIST = "featured_artist", "Featured artist"
        PRODUCER = "producer", "Producer"
        SONGWRITER = "songwriter", "Songwriter"
        COMPOSER = "composer", "Composer"
        MIX_ENGINEER = "mix_engineer", "Mix engineer"
        MASTERING_ENGINEER = "mastering_engineer", "Mastering engineer"
        EXECUTIVE_PRODUCER = "executive_producer", "Executive producer"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="music_credits"
    )
    release = models.ForeignKey(
        Release, null=True, blank=True, on_delete=models.PROTECT, related_name="credits"
    )
    track = models.ForeignKey(
        Track, null=True, blank=True, on_delete=models.PROTECT, related_name="credits"
    )
    name = models.CharField(max_length=241)
    credit_role = models.CharField(max_length=30, choices=Role.choices)
    linked_artist = models.ForeignKey(
        "artists.Artist",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="music_credits",
    )
    linked_contact = models.ForeignKey(
        "contacts.Contact",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="music_credits",
    )
    display_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("display_order", "name")
        constraints = [
            models.CheckConstraint(
                condition=Q(release__isnull=False) | Q(track__isnull=False),
                name="music_credit_has_release_or_track",
            )
        ]

    def clean(self):
        for related in (self.release, self.track, self.linked_artist, self.linked_contact):
            if related and related.organization_id != self.organization_id:
                raise ValidationError("Credit relationships must belong to the same organization.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ReleaseLink(TimestampedModel):
    class Platform(models.TextChoices):
        SPOTIFY = "spotify", "Spotify"
        APPLE_MUSIC = "apple_music", "Apple Music"
        YOUTUBE = "youtube", "YouTube"
        DEEZER = "deezer", "Deezer"
        AUDIOMACK = "audiomack", "Audiomack"
        BOOMPLAY = "boomplay", "Boomplay"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    release = models.ForeignKey(Release, on_delete=models.PROTECT, related_name="links")
    platform = models.CharField(max_length=30, choices=Platform.choices)
    url = models.URLField(max_length=500)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ("-is_primary", "platform")
        constraints = [
            models.UniqueConstraint(
                fields=("release", "platform", "url"), name="unique_release_platform_url"
            ),
            models.UniqueConstraint(
                fields=("release",),
                condition=Q(is_primary=True),
                name="one_primary_link_per_release",
            ),
        ]
