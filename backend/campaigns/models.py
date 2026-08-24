import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TimestampedModel


def active_membership(value, organization_id, field):
    if value and (
        value.organization_id != organization_id or not value.is_active or not value.user.is_active
    ):
        raise ValidationError(
            {field: "Assignment requires an active membership in this organization."}
        )


class Campaign(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        ARCHIVED = "archived", "Archived"

    class Objective(models.TextChoices):
        AWARENESS = "awareness", "Awareness"
        PRE_SAVE = "pre_save", "Pre-save"
        RELEASE_LAUNCH = "release_launch", "Release launch"
        AUDIENCE_GROWTH = "audience_growth", "Audience growth"
        ENGAGEMENT = "engagement", "Engagement"
        STREAMING = "streaming", "Streaming"
        PRESS = "press", "Press"
        LIVE = "live", "Live"
        OTHER = "other", "Other"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="campaigns"
    )
    artist = models.ForeignKey("artists.Artist", on_delete=models.PROTECT, related_name="campaigns")
    release = models.ForeignKey(
        "music.Release", null=True, blank=True, on_delete=models.PROTECT, related_name="campaigns"
    )
    name = models.CharField(max_length=220)
    slug = models.SlugField(max_length=140)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    objective = models.CharField(max_length=30, choices=Objective.choices)
    target_audience = models.CharField(max_length=500, blank=True)
    summary = models.TextField(max_length=10000, blank=True)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    owner_membership = models.ForeignKey(
        "organizations.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="owned_campaigns",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="campaigns_created",
    )

    class Meta:
        ordering = ("-start_date", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "slug"), name="unique_campaign_slug_per_organization"
            )
        ]

    def clean(self):
        if self.artist_id and self.artist.organization_id != self.organization_id:
            raise ValidationError("Campaign Artist must belong to its organization.")
        if self.release_id and (
            self.release.organization_id != self.organization_id
            or self.release.primary_artist_id != self.artist_id
        ):
            raise ValidationError("Campaign Release must belong to the organization and Artist.")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": "End date cannot precede start date."})
        active_membership(self.owner_membership, self.organization_id, "owner_membership")

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if old and old != self.status:
                raise ValidationError("Use the Campaign lifecycle service.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Campaigns cannot be deleted; archive them instead.")

    def __str__(self):
        return self.name


class CampaignChannel(models.Model):
    class Channel(models.TextChoices):
        INSTAGRAM = "instagram", "Instagram"
        TIKTOK = "tiktok", "TikTok"
        YOUTUBE = "youtube", "YouTube"
        X = "x", "X"
        FACEBOOK = "facebook", "Facebook"
        SPOTIFY = "spotify", "Spotify"
        APPLE_MUSIC = "apple_music", "Apple Music"
        DEEZER = "deezer", "Deezer"
        EMAIL = "email", "Email"
        PRESS = "press", "Press"
        RADIO = "radio", "Radio"
        PLAYLISTING = "playlisting", "Playlisting"
        INFLUENCERS = "influencers", "Influencers"
        OOH = "ooh", "Out of home"
        LIVE = "live", "Live"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name="channels")
    channel = models.CharField(max_length=30, choices=Channel.choices)
    notes = models.CharField(max_length=1000, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-is_primary", "channel")
        constraints = [
            models.UniqueConstraint(
                fields=("campaign", "channel"), name="unique_channel_per_campaign"
            ),
            models.UniqueConstraint(
                fields=("campaign",),
                condition=models.Q(is_primary=True),
                name="one_primary_channel_per_campaign",
            ),
        ]

    def __str__(self):
        return f"{self.campaign}: {self.channel}"


class Rollout(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="rollouts"
    )
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name="rollouts")
    name = models.CharField(max_length=220)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    owner_membership = models.ForeignKey(
        "organizations.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="owned_rollouts",
    )
    notes = models.TextField(max_length=10000, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rollouts_created",
    )

    class Meta:
        ordering = ("start_date", "name")

    def clean(self):
        if self.campaign_id and self.campaign.organization_id != self.organization_id:
            raise ValidationError("Rollout Campaign must belong to its organization.")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": "End date cannot precede start date."})
        active_membership(self.owner_membership, self.organization_id, "owner_membership")

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if old and old != self.status:
                raise ValidationError("Use the Rollout lifecycle service.")
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def progress(self):
        tasks = self.tasks.exclude(status=RolloutTask.Status.CANCELLED)
        total = tasks.count()
        return (
            round(tasks.filter(status=RolloutTask.Status.DONE).count() * 100 / total)
            if total
            else 0
        )

    def delete(self, *args, **kwargs):
        raise ValidationError("Rollouts cannot be deleted; archive them instead.")

    def __str__(self):
        return self.name


class RolloutMilestone(TimestampedModel):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        BLOCKED = "blocked", "Blocked"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rollout = models.ForeignKey(Rollout, on_delete=models.PROTECT, related_name="milestones")
    title = models.CharField(max_length=220)
    description = models.TextField(max_length=5000, blank=True)
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    sequence = models.PositiveIntegerField(default=1)
    owner_membership = models.ForeignKey(
        "organizations.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="owned_rollout_milestones",
    )

    class Meta:
        ordering = ("sequence", "target_date", "title")
        constraints = [
            models.UniqueConstraint(
                fields=("rollout", "sequence"), name="unique_milestone_sequence_per_rollout"
            )
        ]

    def clean(self):
        active_membership(
            self.owner_membership,
            self.rollout.organization_id if self.rollout_id else None,
            "owner_membership",
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class RolloutTask(TimestampedModel):
    class Status(models.TextChoices):
        TODO = "todo", "To do"
        IN_PROGRESS = "in_progress", "In progress"
        BLOCKED = "blocked", "Blocked"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rollout = models.ForeignKey(Rollout, on_delete=models.PROTECT, related_name="tasks")
    milestone = models.ForeignKey(
        RolloutMilestone, null=True, blank=True, on_delete=models.PROTECT, related_name="tasks"
    )
    title = models.CharField(max_length=220)
    description = models.TextField(max_length=5000, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    assigned_membership = models.ForeignKey(
        "organizations.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_rollout_tasks",
    )
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_rollout_tasks",
    )
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("sequence", "due_date", "title")

    def clean(self):
        if self.milestone_id and self.milestone.rollout_id != self.rollout_id:
            raise ValidationError("Task Milestone must belong to the same Rollout.")
        active_membership(
            self.assigned_membership,
            self.rollout.organization_id if self.rollout_id else None,
            "assigned_membership",
        )
        if self.status == self.Status.DONE and (not self.completed_at or not self.completed_by_id):
            raise ValidationError("Complete tasks through the completion service.")
        if self.status != self.Status.DONE and (self.completed_at or self.completed_by_id):
            raise ValidationError("Only completed tasks may have completion metadata.")

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if old and old != self.status:
                raise ValidationError("Use the Task lifecycle service.")
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        from django.utils import timezone

        return bool(
            self.due_date
            and self.due_date < timezone.localdate()
            and self.status not in (self.Status.DONE, self.Status.CANCELLED)
        )

    def delete(self, *args, **kwargs):
        raise ValidationError("Tasks cannot be deleted; cancel them instead.")


class RolloutTaskDependency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(RolloutTask, on_delete=models.PROTECT, related_name="dependencies")
    depends_on = models.ForeignKey(RolloutTask, on_delete=models.PROTECT, related_name="dependents")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("task", "depends_on"), name="unique_rollout_task_dependency"
            ),
            models.CheckConstraint(
                condition=~models.Q(task=models.F("depends_on")),
                name="task_cannot_depend_on_itself",
            ),
        ]

    def __str__(self):
        return f"{self.task} depends on {self.depends_on}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.task_id == self.depends_on_id:
            raise ValidationError("A task cannot depend on itself.")
        if (
            self.task_id
            and self.depends_on_id
            and self.task.rollout_id != self.depends_on.rollout_id
        ):
            raise ValidationError("Dependencies must belong to the same Rollout.")
        pending = [self.depends_on_id]
        seen = set()
        while pending:
            current_id = pending.pop()
            if current_id == self.task_id:
                raise ValidationError("Task dependency would create a cycle.")
            if current_id in seen:
                continue
            seen.add(current_id)
            pending.extend(
                RolloutTaskDependency.objects.filter(task_id=current_id).values_list(
                    "depends_on_id", flat=True
                )
            )
