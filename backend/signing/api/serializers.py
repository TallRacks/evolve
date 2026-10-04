from django.core.validators import validate_email
from rest_framework import serializers

from signing.models import SigningEvent, SigningRequest


class SigningRequestSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        organization = self.context.get("organization")
        for field_name in ("source_document", "source_contract"):
            source = attrs.get(field_name)
            if source and organization and source.organization_id != organization.id:
                raise serializers.ValidationError(
                    {field_name: "The selected source must belong to this organization."}
                )
        booking = attrs.get("booking")
        if booking and booking.organization_id != organization.id:
            raise serializers.ValidationError({"booking": "The selected Booking must belong to this organization."})
        if (
            not attrs.get("source_document")
            and not attrs.get("source_contract")
            and not attrs.get("template_key")
        ):
            raise serializers.ValidationError(
                "Choose a source document, source contract, or template key."
            )
        return attrs

    def validate_signers(self, value):
        if not value:
            raise serializers.ValidationError("Add at least one signer.")
        for signer in value:
            if not isinstance(signer, dict) or not signer.get("email"):
                raise serializers.ValidationError("Each signer needs an email address.")
            validate_email(str(signer["email"]))
        return value

    class Meta:
        model = SigningRequest
        fields = (
            "id", "organization", "booking", "source_document", "source_contract", "title",
            "template_key", "status", "provider", "provider_document_id", "signing_url",
            "completed_document_url", "signers", "last_event_at", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "organization", "status", "provider", "provider_document_id", "signing_url",
            "completed_document_url", "last_event_at", "created_at", "updated_at",
        )


class SigningEventSerializer(serializers.Serializer):
    event_id = serializers.CharField(required=False, allow_blank=True, max_length=220)
    event_type = serializers.CharField(max_length=100)
    status = serializers.ChoiceField(choices=SigningRequest.Status.choices)
    provider_document_id = serializers.CharField(required=False, allow_blank=True, max_length=220)
    signing_url = serializers.URLField(required=False, allow_blank=True)
    completed_document_url = serializers.URLField(required=False, allow_blank=True)
    signers = serializers.ListField(required=False)


class SigningEventResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SigningEvent
        fields = ('id', 'provider_event_id', 'event_type', 'status', 'payload_digest', 'created_at')
        read_only_fields = fields
