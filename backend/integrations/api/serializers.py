from rest_framework import serializers

from integrations.models import EmailConnector, StorageProvider


class EmailConnectorSerializer(serializers.ModelSerializer):
    secret_configured = serializers.BooleanField(read_only=True)

    class Meta:
        model = EmailConnector
        exclude = ("created_by",)
        read_only_fields = (
            "id",
            "connection_status",
            "last_tested_at",
            "last_test_message",
            "created_at",
            "updated_at",
            "secret_configured",
        )


class StorageProviderSerializer(serializers.ModelSerializer):
    credentials_configured = serializers.BooleanField(read_only=True)

    class Meta:
        model = StorageProvider
        exclude = ("created_by",)
        read_only_fields = (
            "id",
            "connection_status",
            "last_tested_at",
            "last_test_message",
            "created_at",
            "updated_at",
            "credentials_configured",
        )


class TestEmailSerializer(serializers.Serializer):
    recipient = serializers.EmailField()
