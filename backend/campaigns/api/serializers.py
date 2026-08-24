from rest_framework import serializers

from campaigns.models import (
    Campaign,
    CampaignChannel,
    Rollout,
    RolloutMilestone,
    RolloutTask,
)


class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignChannel
        exclude = ("campaign",)
        read_only_fields = ("id", "created_at")


class CampaignSummarySerializer(serializers.ModelSerializer):
    artist = serializers.CharField(source="artist.stage_name")
    release_title = serializers.CharField(source="release.title", allow_null=True)
    owner = serializers.SerializerMethodField()
    rollout_progress = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = (
            "id",
            "organization_id",
            "artist_id",
            "artist",
            "release_id",
            "release_title",
            "name",
            "slug",
            "status",
            "objective",
            "priority",
            "start_date",
            "end_date",
            "owner",
            "rollout_progress",
        )

    def get_owner(self, o):
        return (
            " ".join(
                filter(
                    None, (o.owner_membership.user.first_name, o.owner_membership.user.last_name)
                )
            )
            or o.owner_membership.user.email
            if o.owner_membership
            else None
        )

    def get_rollout_progress(self, o):
        values = [r.progress for r in o.rollouts.all()]
        return round(sum(values) / len(values)) if values else 0


class CampaignWriteSerializer(serializers.ModelSerializer):
    artist_id = serializers.UUIDField()
    release_id = serializers.UUIDField(required=False, allow_null=True)
    owner_membership_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Campaign
        exclude = (
            "organization",
            "artist",
            "release",
            "owner_membership",
            "created_by",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {"status": {"read_only": True}}


class MilestoneSerializer(serializers.ModelSerializer):
    owner_membership_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = RolloutMilestone
        exclude = ("rollout", "owner_membership")
        read_only_fields = ("id", "created_at", "updated_at")


class TaskSerializer(serializers.ModelSerializer):
    milestone_id = serializers.UUIDField(required=False, allow_null=True)
    assigned_membership_id = serializers.UUIDField(required=False, allow_null=True)
    is_overdue = serializers.BooleanField(read_only=True)
    assignee = serializers.SerializerMethodField()
    milestone_title = serializers.CharField(source="milestone.title", read_only=True)
    dependencies = serializers.SerializerMethodField()

    class Meta:
        model = RolloutTask
        exclude = ("rollout", "milestone", "assigned_membership", "completed_by")
        read_only_fields = ("id", "status", "completed_at", "created_at", "updated_at")

    def get_assignee(self, o):
        return (
            o.assigned_membership.user.get_full_name() or o.assigned_membership.user.email
            if o.assigned_membership
            else None
        )

    def get_dependencies(self, o):
        return [
            {"id": d.id, "task_id": d.depends_on_id, "title": d.depends_on.title}
            for d in o.dependencies.select_related("depends_on")
        ]


class RolloutSummarySerializer(serializers.ModelSerializer):
    campaign_name = serializers.CharField(source="campaign.name")
    progress = serializers.IntegerField()
    owner = serializers.SerializerMethodField()

    class Meta:
        model = Rollout
        fields = (
            "id",
            "organization_id",
            "campaign_id",
            "campaign_name",
            "name",
            "status",
            "start_date",
            "end_date",
            "owner",
            "progress",
        )

    def get_owner(self, o):
        return (
            " ".join(
                filter(
                    None, (o.owner_membership.user.first_name, o.owner_membership.user.last_name)
                )
            )
            or o.owner_membership.user.email
            if o.owner_membership
            else None
        )


class RolloutWriteSerializer(serializers.ModelSerializer):
    owner_membership_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Rollout
        exclude = (
            "organization",
            "campaign",
            "owner_membership",
            "created_by",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {"status": {"read_only": True}}


class RolloutDetailSerializer(RolloutSummarySerializer):
    milestones = MilestoneSerializer(many=True)
    tasks = TaskSerializer(many=True)
    activity = serializers.ListField()
    notes = serializers.CharField()

    class Meta:
        model = Rollout
        fields = RolloutSummarySerializer.Meta.fields + ("notes", "milestones", "tasks", "activity")


class CampaignDetailSerializer(CampaignSummarySerializer):
    channels = ChannelSerializer(many=True)
    rollouts = RolloutSummarySerializer(many=True)
    activity = serializers.ListField()
    target_audience = serializers.CharField()
    summary = serializers.CharField()
    allowed_transitions = serializers.ListField()

    class Meta:
        model = Campaign
        fields = CampaignSummarySerializer.Meta.fields + (
            "target_audience",
            "summary",
            "channels",
            "rollouts",
            "activity",
            "allowed_transitions",
        )


class StatusSerializer(serializers.Serializer):
    to_status = serializers.CharField()


class DeveloperCampaignSerializer(serializers.ModelSerializer):
    artist = serializers.CharField(source="artist.stage_name")
    release = serializers.CharField(source="release.title", allow_null=True)

    class Meta:
        model = Campaign
        fields = (
            "id",
            "name",
            "artist",
            "release",
            "objective",
            "status",
            "start_date",
            "end_date",
        )


class DeveloperRolloutSerializer(serializers.ModelSerializer):
    campaign = serializers.CharField(source="campaign.name")
    progress = serializers.IntegerField()

    class Meta:
        model = Rollout
        fields = ("id", "campaign", "name", "status", "start_date", "end_date", "progress")


class PortalCampaignSerializer(serializers.ModelSerializer):
    rollout_progress = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = (
            "id",
            "artist_id",
            "name",
            "status",
            "objective",
            "start_date",
            "end_date",
            "rollout_progress",
        )

    def get_rollout_progress(self, campaign):
        values = [rollout.progress for rollout in campaign.rollouts.all()]
        return round(sum(values) / len(values)) if values else 0
