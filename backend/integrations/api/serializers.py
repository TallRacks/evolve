from rest_framework import serializers

from integrations.models import EmailConnector, GoogleWorkspaceConnector, StorageProvider


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
    stored_document_count = serializers.IntegerField(
        source="stored_documents.count", read_only=True
    )
    managed_bytes = serializers.SerializerMethodField()

    def get_managed_bytes(self, obj):
        from django.db.models import Sum

        return obj.stored_documents.aggregate(total=Sum("file_size"))["total"] or 0

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
            "stored_document_count",
            "managed_bytes",
        )


class TestEmailSerializer(serializers.Serializer):
    recipient = serializers.EmailField()


class GoogleWorkspaceConnectorSerializer(serializers.ModelSerializer):
    credentials_configured = serializers.BooleanField(read_only=True)

    class Meta:
        model = GoogleWorkspaceConnector
        exclude = ("created_by",)
        read_only_fields = (
            "id", "connection_status", "last_tested_at", "last_test_message",
            "created_at", "updated_at", "credentials_configured",
        )
