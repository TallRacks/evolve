from rest_framework import serializers

from organizations.models import Membership
from tasks.models import Task, TaskChecklistItem


class ChecklistSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskChecklistItem
        fields = ("id", "title", "sequence", "is_completed", "completed_at")
        read_only_fields = ("id", "is_completed", "completed_at")


class TaskSerializer(serializers.ModelSerializer):
    assigned_membership_id = serializers.PrimaryKeyRelatedField(
        source="assigned_membership",
        queryset=Membership.objects.all(),
        required=False,
        allow_null=True,
    )
    assignee = serializers.SerializerMethodField()
    progress = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    checklist_items = ChecklistSerializer(many=True, read_only=True)
    context = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = (
            "id",
            "organization_id",
            "title",
            "description",
            "status",
            "priority",
            "assigned_membership_id",
            "assignee",
            "due_at",
            "completed_at",
            "sequence",
            "artist",
            "booking",
            "release",
            "campaign",
            "rollout",
            "production_advance",
            "travel_itinerary",
            "contract",
            "source_document",
            "context",
            "progress",
            "is_overdue",
            "checklist_items",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "source_document",
            "status",
            "completed_at",
            "created_at",
            "updated_at",
        )

    def get_assignee(self, task):
        if not task.assigned_membership:
            return None
        user = task.assigned_membership.user
        return {
            "id": task.assigned_membership_id,
            "name": f"{user.first_name} {user.last_name}".strip() or user.email,
        }

    def get_context(self, task):
        for field, label in (
            ("release", "Release"),
            ("booking", "Booking"),
            ("artist", "Artist"),
            ("campaign", "Campaign"),
            ("rollout", "Rollout"),
            ("production_advance", "Production"),
            ("travel_itinerary", "Travel"),
            ("contract", "Contract"),
        ):
            value = getattr(task, field)
            if value:
                return {"type": field, "label": label, "id": value.pk, "name": str(value)}
        return None


class TaskTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Task.Status.choices)
