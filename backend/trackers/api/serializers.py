from rest_framework import serializers

from trackers.models import Tracker, TrackerSyncEvent


class TrackerSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(write_only=True, required=False)
    organization = serializers.PrimaryKeyRelatedField(read_only=True)
    schema_state = serializers.JSONField(read_only=True)

    class Meta:
        model = Tracker
        fields = "__all__"
        read_only_fields = ("id", "organization", "last_synced_at", "last_sync_status", "last_sync_message", "created_by", "schema_state")

    def create(self, validated_data):
        # The API scopes organization server-side. Do not pass the client hint
        # through to Django as a second organization assignment.
        validated_data.pop("organization_id", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("organization_id", None)
        return super().update(instance, validated_data)

    def validate_google_connector(self, connector):
        if not connector.is_active:
            raise serializers.ValidationError("Activate the Google Workspace connector before creating a tracker.")
        if "sheets" not in (connector.products or []):
            raise serializers.ValidationError("The selected Google connector must include Sheets.")
        return connector


class TrackerSyncEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackerSyncEvent
        fields = "__all__"
