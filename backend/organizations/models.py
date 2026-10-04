import uuid

from django.conf import settings
from django.db import models

from core.models import TimestampedModel


class Organization(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class RoleProfile(TimestampedModel):
    """Organization-owned role definition for page and capability access."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="role_profiles"
    )
    key = models.SlugField(max_length=80)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=500, blank=True)
    permissions = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=("organization", "key"), name="unique_org_role_profile_key")
        ]

    def __str__(self):
        return f"{self.organization} / {self.name}"


class FeatureSetting(TimestampedModel):
    """Organization-owned feature switch; authorization remains permission based."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="feature_settings"
    )
    key = models.SlugField(max_length=100)
    label = models.CharField(max_length=140)
    description = models.CharField(max_length=500, blank=True)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ("label",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "key"), name="unique_org_feature_setting"
            )
        ]

    def __str__(self):
        return f"{self.organization} / {self.label}"


class MembershipQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True, organization__is_active=True, user__is_active=True)


class Membership(TimestampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Administrator"
        MANAGER = "manager", "Manager"
        MEMBER = "member", "Member"
        ARTIST = "artist", "Artist"
        ARTIST_MANAGER = "artist_manager", "Artist manager"
        ARTIST_ASSISTANT = "artist_assistant", "Artist assistant"
        ARTIST_VIEWER = "artist_viewer", "Artist viewer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    permission_overrides = models.JSONField(default=dict, blank=True)
    role_profile = models.ForeignKey(
        "organizations.RoleProfile", null=True, blank=True, on_delete=models.PROTECT, related_name="memberships"
    )
    is_active = models.BooleanField(default=True)

    objects = MembershipQuerySet.as_manager()

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("user", "organization"), name="unique_user_organization_membership"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.organization} ({self.get_role_display()})"


class Invitation(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Membership.Role.choices)
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invitations",
    )
    expires_at = models.DateTimeField(editable=False)
    accepted_at = models.DateTimeField(null=True, blank=True, editable=False)
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("organization", "email"))]

    def __str__(self) -> str:
        return f"{self.email} invited to {self.organization}"
