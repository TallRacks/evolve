import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TimestampedModel


class Comment(TimestampedModel):
    class Context(models.TextChoices):
        DOCUMENT = "document", "Document"
        TASK = "task", "Task"
        BOOKING = "booking", "Booking"
        CAMPAIGN = "campaign", "Campaign"
        PRODUCTION = "production", "Production"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="comments"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="comments"
    )
    context_type = models.CharField(max_length=20, choices=Context.choices)
    context_id = models.UUIDField()
    parent_comment = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="replies"
    )
    body = models.TextField(max_length=5000)
    edited_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="comments_resolved",
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if not self.body.strip():
            raise ValidationError({"body": "Comment text is required."})


class CommentMention(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comment = models.ForeignKey(Comment, on_delete=models.PROTECT, related_name="mentions")
    membership = models.ForeignKey(
        "organizations.Membership", on_delete=models.PROTECT, related_name="comment_mentions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("comment", "membership"), name="unique_comment_mention")
        ]

    def __str__(self):
        return f"{self.comment_id}:{self.membership_id}"
