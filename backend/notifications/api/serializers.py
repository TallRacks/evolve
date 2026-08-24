from rest_framework import serializers

from notifications.models import NotificationPreference, NotificationRecipient


class RecipientSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="notification.id")
    notification_type = serializers.CharField(source="notification.notification_type")
    category = serializers.CharField(source="notification.category")
    title = serializers.CharField(source="notification.title")
    message = serializers.CharField(source="notification.message")
    priority = serializers.CharField(source="notification.priority")
    source_type = serializers.CharField(source="notification.source_type")
    action_url = serializers.CharField(source="notification.action_url")
    organization = serializers.CharField(source="notification.organization.name", allow_null=True)
    created_at = serializers.DateTimeField(source="notification.created_at")

    class Meta:
        model = NotificationRecipient
        fields = (
            "id",
            "notification_type",
            "category",
            "title",
            "message",
            "priority",
            "source_type",
            "action_url",
            "organization",
            "created_at",
            "read_at",
        )


class ReadSerializer(serializers.Serializer):
    read = serializers.BooleanField(default=True)


class PreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ("category", "in_app_enabled")
