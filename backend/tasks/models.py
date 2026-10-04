import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import TimestampedModel


class Task(TimestampedModel):
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
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="tasks"
    )
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, max_length=5000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    assigned_membership = models.ForeignKey(
        "organizations.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_tasks",
    )
    additional_assignees = models.ManyToManyField("organizations.Membership", blank=True, related_name="shared_tasks")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="tasks_created"
    )
    source_document = models.ForeignKey(
        "documents.Document",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="source_tasks",
    )
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks_completed",
    )
    sequence = models.PositiveIntegerField(default=1)
    archived_at = models.DateTimeField(null=True, blank=True)
    artist = models.ForeignKey(
        "artists.Artist", null=True, blank=True, on_delete=models.PROTECT, related_name="tasks"
    )
    booking = models.ForeignKey(
        "bookings.Booking", null=True, blank=True, on_delete=models.PROTECT, related_name="tasks"
    )
    release = models.ForeignKey(
        "music.Release", null=True, blank=True, on_delete=models.PROTECT, related_name="tasks"
    )
    campaign = models.ForeignKey(
        "campaigns.Campaign", null=True, blank=True, on_delete=models.PROTECT, related_name="tasks"
    )
    rollout = models.ForeignKey(
        "campaigns.Rollout",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="workflow_tasks",
    )
    production_advance = models.ForeignKey(
        "production.ProductionAdvance",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="tasks",
    )
    travel_itinerary = models.ForeignKey(
        "travel.TravelItinerary",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="tasks",
    )
    contract = models.ForeignKey(
        "contracts.Contract", null=True, blank=True, on_delete=models.PROTECT, related_name="tasks"
    )

    class Meta:
        ordering = ("status", "due_at", "sequence", "title")
        indexes = [
            models.Index(fields=("organization", "status", "due_at")),
            models.Index(fields=("assigned_membership", "status")),
        ]

    @property
    def is_overdue(self):
        return bool(
            self.due_at
            and self.due_at < timezone.now()
            and self.status not in {self.Status.DONE, self.Status.CANCELLED}
        )

    @property
    def progress(self):
        active = self.checklist_items.filter(removed_at__isnull=True)
        total = active.count()
        complete = active.filter(is_completed=True).count()
        return {
            "complete": complete,
            "total": total,
            "percent": round(complete * 100 / total) if total else 0,
        }

    def clean(self):
        context_fields = (
            "artist",
            "booking",
            "release",
            "campaign",
            "rollout",
            "production_advance",
            "travel_itinerary",
            "contract",
        )
        if sum(bool(getattr(self, field + "_id")) for field in context_fields) > 1:
            raise ValidationError("A Task may have only one context.")
        if self.assigned_membership_id and (
            self.assigned_membership.organization_id != self.organization_id
            or not self.assigned_membership.is_active
            or not self.assigned_membership.user.is_active
        ):
            raise ValidationError(
                {"assigned_membership": "Use an active membership from this organization."}
            )
        if self.pk and self.additional_assignees.filter(organization_id=self.organization_id, is_active=True, user__is_active=True).count() != self.additional_assignees.count():
            raise ValidationError({"additional_assignees": "Use active members from this organization."})
        if self.source_document_id and self.source_document.organization_id != self.organization_id:
            raise ValidationError("Source Document must belong to the task organization.")
        contexts = [
            self.artist,
            self.booking,
            self.release,
            self.campaign,
            self.rollout,
            self.production_advance,
            self.travel_itinerary,
            self.contract,
        ]
        for context in (item for item in contexts if item):
            if context.organization_id != self.organization_id:
                raise ValidationError("Task context must belong to its organization.")
        if self.status == self.Status.DONE and (not self.completed_at or not self.completed_by_id):
            raise ValidationError("Complete tasks through the lifecycle service.")
        if self.status != self.Status.DONE and (self.completed_at or self.completed_by_id):
            raise ValidationError("Only completed tasks may retain completion metadata.")

    def save(self, *args, **kwargs):
        if self.pk:
            previous = (
                type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )
            if previous and previous != self.status:
                raise ValidationError("Use the Task lifecycle service.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Tasks cannot be deleted; cancel or archive them instead.")

    def __str__(self):
        return self.title


class TaskChecklistItem(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name="checklist_items")
    title = models.CharField(max_length=220)
    sequence = models.PositiveIntegerField(default=1)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="task_checklist_items_completed",
    )
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("sequence", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("task", "sequence"),
                condition=Q(removed_at__isnull=True),
                name="unique_active_task_checklist_sequence",
            )
        ]

    def clean(self):
        if self.is_completed != bool(self.completed_at and self.completed_by_id):
            raise ValidationError(
                "Checklist completion metadata must be changed through its service."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Checklist items are removed semantically.")

    def __str__(self):
        return self.title
