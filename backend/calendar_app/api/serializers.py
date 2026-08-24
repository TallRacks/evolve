from rest_framework import serializers

from calendar_app.models import CalendarEvent


class EventSerializer(serializers.ModelSerializer):
    artist_name = serializers.CharField(source="artist.stage_name", read_only=True)
    owner_email = serializers.EmailField(source="owner_membership.user.email", read_only=True)

    class Meta:
        model = CalendarEvent
        fields = (
            "id",
            "organization",
            "title",
            "event_type",
            "description",
            "starts_at",
            "ends_at",
            "all_day",
            "timezone",
            "artist",
            "artist_name",
            "owner_membership",
            "owner_email",
            "location",
            "visibility",
            "status",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "status",
            "created_by",
            "created_at",
            "updated_at",
        )
