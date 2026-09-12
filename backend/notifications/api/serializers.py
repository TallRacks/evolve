from rest_framework import serializers

from notifications.models import EmailDeliveryAttempt, NotificationPreference, NotificationRecipient


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
    email_status = serializers.SerializerMethodField()

    def get_email_status(self, obj):
        attempt = next(
            (item for item in obj.notification.email_attempts.all() if item.user_id == obj.user_id),
            None,
        )
        return attempt.status if attempt else None

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
            "email_status",
        )


class ReadSerializer(serializers.Serializer):
    read = serializers.BooleanField(default=True)


class PreferenceSerializer(serializers.ModelSerializer):
    in_app_enabled = serializers.BooleanField(required=False)
    email_enabled = serializers.BooleanField(required=False)

    class Meta:
        model = NotificationPreference
        fields = ("category", "in_app_enabled", "email_enabled")


class DeliveryAttemptSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    connector_name = serializers.CharField(source="connector.name", read_only=True)

    class Meta:
        model = EmailDeliveryAttempt
        fields = (
            "id",
            "notification",
            "user",
            "organization",
            "organization_name",
            "connector",
            "connector_name",
            "category",
            "template_key",
            "recipient_email_snapshot",
            "subject_snapshot",
            "status",
            "failure_code",
            "failure_message",
            "attempt_number",
            "attempted_at",
            "sent_at",
        )
