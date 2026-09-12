import hashlib
import json
import uuid

from django.conf import settings
from django.db import models

from core.models import TimestampedModel
from .automation_models import AutomationExecution
from .channel_models import (
    ChannelVerification,
    InboundMessage,
    MessagingConnector,
    MessagingIdentity,
)
from .collaboration_models import Comment, CommentMention


class ActionRequest(TimestampedModel):
    class Risk(models.TextChoices):
        READ = "read", "Read only"
        LOW = "low", "Low risk"
        MEDIUM = "medium", "Medium risk"
        HIGH = "high", "High risk"

    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        EXECUTED = "executed", "Executed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"
        FAILED = "failed", "Failed"
        BLOCKED = "blocked", "Blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    channel = models.CharField(max_length=32, default="copilot")
    action_key = models.CharField(max_length=80)
    risk = models.CharField(max_length=16, choices=Risk.choices)
    validated_payload = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROPOSED)
    confirmation_hash = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField()
    executed_at = models.DateTimeField(null=True, blank=True)
    result_summary = models.CharField(max_length=500, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True)

    class Meta:
        indexes = [models.Index(fields=("organization", "status", "expires_at"))]

    @staticmethod
    def make_confirmation_hash(
        *, actor_id, organization_id, channel, action_key, payload, expires_at
    ):
        value = json.dumps(
            {
                "actor": str(actor_id),
                "organization": str(organization_id),
                "channel": channel,
                "action": action_key,
                "payload": payload,
                "expires": expires_at.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(value.encode()).hexdigest()


class AIProviderConfig(TimestampedModel):
    provider_name = models.CharField(max_length=80)
    model = models.CharField(max_length=120)
    secret_reference = models.CharField(max_length=110, blank=True)
    is_active = models.BooleanField(default=False)
    status = models.CharField(max_length=24, default="not_configured")
    last_tested_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)


class Automation(TimestampedModel):
    name = models.CharField(max_length=160)
    event_key = models.CharField(max_length=80)
    condition = models.JSONField(default=dict, blank=True)
    action_key = models.CharField(max_length=80)
    action_config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=False)
    last_run_at = models.DateTimeField(null=True, blank=True)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class Workspace(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="workspaces"
    )
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True, max_length=2000)
    icon = models.CharField(max_length=40, blank=True)
    archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="workspaces_created",
    )

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "slug"), name="unique_workspace_slug_per_org"
            )
        ]


class Board(TimestampedModel):
    class Source(models.TextChoices):
        TASKS = "tasks", "Tasks"
        BOOKINGS = "bookings", "Bookings"
        PRODUCTION = "production", "Production"
        CAMPAIGN_ROLLOUT = "campaign_rollout", "Campaigns and Rollouts"
        RELEASES = "releases", "Releases"

    class View(models.TextChoices):
        LIST = "list", "List"
        BOARD = "board", "Board"
        CALENDAR = "calendar", "Calendar"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="boards")
    name = models.CharField(max_length=160)
    source_type = models.CharField(max_length=32, choices=Source.choices)
    description = models.TextField(blank=True, max_length=1000)
    default_view = models.CharField(max_length=16, choices=View.choices, default=View.LIST)
    archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="boards_created",
    )

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "name"), name="unique_board_name_per_workspace"
            )
        ]
