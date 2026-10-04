import re
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel

HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
HOSTNAME = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def validate_hex_color(value):
    if not HEX_COLOR.fullmatch(value):
        raise ValidationError("Use a six-digit hexadecimal color such as #D6A84B.")


def validate_hostname(value):
    if not HOSTNAME.fullmatch(value.lower().rstrip(".")):
        raise ValidationError("Enter a valid fully qualified hostname.")


def _relative_luminance(color):
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def validate_theme_contrast(colors):
    def ratio(first, second):
        light, dark = sorted(
            (_relative_luminance(first), _relative_luminance(second)), reverse=True
        )
        return (light + 0.05) / (dark + 0.05)

    checks = (
        ("text_color", "background_color", 4.5),
        ("text_color", "surface_color", 4.5),
        ("text_muted_color", "background_color", 4.5),
        ("primary_color", "background_color", 3),
        ("accent_color", "background_color", 3),
    )
    for foreground, background, minimum in checks:
        if ratio(colors[foreground], colors[background]) < minimum:
            raise ValidationError(
                {foreground: f"Contrast against {background.replace(chr(95), chr(32))} is too low."}
            )


class OrganizationBranding(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.CASCADE, related_name="branding"
    )
    display_name = models.CharField(max_length=120, blank=True)
    logo_url = models.URLField(max_length=500, blank=True)
    favicon_url = models.URLField(max_length=500, blank=True)
    primary_color = models.CharField(
        max_length=7, default="#D6A84B", validators=[validate_hex_color]
    )
    secondary_color = models.CharField(
        max_length=7, default="#A3A3A3", validators=[validate_hex_color]
    )
    accent_color = models.CharField(
        max_length=7, default="#F0C96B", validators=[validate_hex_color]
    )
    background_color = models.CharField(
        max_length=7, default="#0A0A0A", validators=[validate_hex_color]
    )
    surface_color = models.CharField(
        max_length=7, default="#171717", validators=[validate_hex_color]
    )
    text_color = models.CharField(max_length=7, default="#FAFAFA", validators=[validate_hex_color])
    text_muted_color = models.CharField(
        max_length=7, default="#A3A3A3", validators=[validate_hex_color]
    )
    seo_title = models.CharField(max_length=160, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)
    og_image_url = models.URLField(max_length=500, blank=True)
    support_email = models.EmailField(blank=True)
    support_url = models.URLField(max_length=500, blank=True)

    def clean(self):
        validate_theme_contrast(
            {
                "primary_color": self.primary_color,
                "accent_color": self.accent_color,
                "background_color": self.background_color,
                "surface_color": self.surface_color,
                "text_color": self.text_color,
                "text_muted_color": self.text_muted_color,
            }
        )

    class Meta:
        ordering = ("organization__name",)

    def __str__(self):
        return self.display_name or self.organization.name


class GlobalBranding(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    override_organizations = models.BooleanField(default=True)
    display_name = models.CharField(max_length=120, blank=True)
    application_title = models.CharField(max_length=120, blank=True)
    logo_url = models.URLField(max_length=500, blank=True)
    favicon_url = models.URLField(max_length=500, blank=True)
    mobile_icon_url = models.URLField(max_length=500, blank=True)
    primary_color = models.CharField(max_length=7, blank=True, validators=[validate_hex_color])
    secondary_color = models.CharField(max_length=7, blank=True, validators=[validate_hex_color])
    accent_color = models.CharField(max_length=7, blank=True, validators=[validate_hex_color])
    background_color = models.CharField(max_length=7, blank=True, validators=[validate_hex_color])
    surface_color = models.CharField(max_length=7, blank=True, validators=[validate_hex_color])
    text_color = models.CharField(max_length=7, blank=True, validators=[validate_hex_color])
    text_muted_color = models.CharField(max_length=7, blank=True, validators=[validate_hex_color])
    seo_title = models.CharField(max_length=160, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)
    og_image_url = models.URLField(max_length=500, blank=True)
    support_email = models.EmailField(blank=True)
    support_url = models.URLField(max_length=500, blank=True)

    class Meta:
        ordering = ("-updated_at",)

    def clean(self):
        colors = {name: getattr(self, name) for name in ("primary_color", "accent_color", "background_color", "surface_color", "text_color", "text_muted_color")}
        if all(colors.values()):
            validate_theme_contrast(colors)

    def __str__(self):
        return self.display_name or "Global branding"


class GlobalBrandingAsset(TimestampedModel):
    class AssetType(models.TextChoices):
        LOGO = "logo", "Logo"
        DARK_LOGO = "dark_logo", "Dark-mode logo"
        FAVICON = "favicon", "Favicon"
        MOBILE_ICON = "mobile_icon", "Mobile/home-screen icon"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branding = models.ForeignKey(
        GlobalBranding, on_delete=models.CASCADE, related_name="assets"
    )
    asset_type = models.CharField(max_length=20, choices=AssetType.choices)
    storage_provider = models.ForeignKey(
        "integrations.StorageProvider", on_delete=models.PROTECT, related_name="global_branding_assets"
    )
    storage_key = models.CharField(max_length=512)
    original_filename = models.CharField(max_length=180)
    content_type = models.CharField(max_length=120)
    file_size = models.PositiveBigIntegerField()
    checksum_sha256 = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("branding", "asset_type"), name="one_global_branding_asset_per_type"
            )
        ]
        ordering = ("asset_type",)

    def __str__(self):
        return f"{self.branding} {self.get_asset_type_display()}"


class OrganizationDomain(TimestampedModel):
    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="domains"
    )
    hostname = models.CharField(max_length=253, unique=True, validators=[validate_hostname])
    verification_status = models.CharField(
        max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.PENDING
    )
    verification_token = models.CharField(max_length=64, editable=False)
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    is_active = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ("hostname",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization",),
                condition=Q(is_active=True, is_primary=True),
                name="one_active_primary_domain_per_organization",
            )
        ]

    def clean(self):
        self.hostname = self.hostname.lower().rstrip(".")
        validate_hostname(self.hostname)
        if self.is_active and self.verification_status != self.VerificationStatus.VERIFIED:
            raise ValidationError("Only verified domains can be activated.")
        if self.is_primary and not self.is_active:
            raise ValidationError("A primary domain must be active.")

    def save(self, *args, **kwargs):
        self.hostname = self.hostname.lower().rstrip(".")
        super().save(*args, **kwargs)

    @property
    def verification_name(self):
        return f"_evolve-verification.{self.hostname}"

    def __str__(self):
        return self.hostname


class APIClient(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="api_clients"
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, max_length=1000)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="api_clients_created",
    )

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return f"{self.organization}: {self.name}"


class APIKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(APIClient, on_delete=models.CASCADE, related_name="keys")
    key_prefix = models.CharField(max_length=16, unique=True)
    secret_digest = models.CharField(max_length=64, unique=True, editable=False)
    scopes = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.client.name}: {self.key_prefix}"
