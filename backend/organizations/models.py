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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
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
