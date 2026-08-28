from rest_framework import serializers

from contracts.models import (
    Contract,
    ContractApproval,
    ContractDocument,
    ContractParty,
    ContractSection,
    ContractTerm,
)
from contracts.services import TRANSITIONS, execution_errors


class PartySerializer(serializers.ModelSerializer):
    source_type = serializers.SerializerMethodField()

    class Meta:
        model = ContractParty
        fields = (
            "id",
            "role",
            "display_name",
            "linked_artist",
            "linked_promoter",
            "linked_contact",
            "linked_rights_party",
            "legal_name",
            "email_snapshot",
            "address_snapshot",
            "is_signatory",
            "signing_status",
            "signing_order",
            "signed_at",
            "signing_note",
            "source_type",
        )
        read_only_fields = ("id", "signing_status", "signed_at", "signing_note", "source_type")

    def get_source_type(self, obj):
        for field in ("linked_artist", "linked_promoter", "linked_contact", "linked_rights_party"):
            if getattr(obj, f"{field}_id"):
                return field.removeprefix("linked_")
        return "external"


class TermSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractTerm
        fields = (
            "id",
            "term_type",
            "title",
            "value_text",
            "value_decimal",
            "currency",
            "date_value",
            "boolean_value",
            "notes",
            "sequence",
        )
        read_only_fields = ("id",)


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractSection
        fields = ("id", "section_type", "title", "body", "sequence")
        read_only_fields = ("id",)


class ApprovalSerializer(serializers.ModelSerializer):
    approver = serializers.CharField(source="membership.user.email", read_only=True)
    decided_by_name = serializers.CharField(source="decided_by.email", read_only=True, default="")

    class Meta:
        model = ContractApproval
        fields = (
            "id",
            "membership",
            "approver",
            "status",
            "requested_at",
            "decided_at",
            "decided_by_name",
            "comment",
            "sequence",
        )
        read_only_fields = fields


class DocumentSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="document.id")
    title = serializers.CharField(source="document.title")
    external_url = serializers.URLField(source="document.external_url")
    link_id = serializers.UUIDField(source="id")

    class Meta:
        model = ContractDocument
        fields = ("id", "title", "external_url", "link_id")


class ContractWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = (
            "title",
            "contract_type",
            "artist",
            "booking",
            "promoter",
            "effective_date",
            "expiry_date",
            "signed_date",
            "currency",
            "total_value",
            "governing_law",
            "jurisdiction",
            "summary",
            "internal_notes",
        )
        extra_kwargs = {
            "artist": {
                "queryset": Contract.artist.field.related_model.objects.all(),
                "allow_null": True,
            },
            "booking": {
                "queryset": Contract.booking.field.related_model.objects.all(),
                "allow_null": True,
            },
            "promoter": {
                "queryset": Contract.promoter.field.related_model.objects.all(),
                "allow_null": True,
            },
        }


class ContractListSerializer(serializers.ModelSerializer):
    artist_name = serializers.CharField(source="artist.stage_name", read_only=True, default="")
    booking_reference = serializers.CharField(
        source="booking.reference", read_only=True, default=""
    )
    promoter_name = serializers.CharField(source="promoter.name", read_only=True, default="")
    counterparty = serializers.SerializerMethodField()
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Contract
        fields = (
            "id",
            "organization",
            "reference",
            "title",
            "contract_type",
            "status",
            "artist",
            "artist_name",
            "booking",
            "booking_reference",
            "promoter",
            "promoter_name",
            "counterparty",
            "effective_date",
            "expiry_date",
            "is_expired",
            "updated_at",
        )

    def get_counterparty(self, obj):
        party = next((x for x in obj.parties.all() if x.role != "artist"), None)
        return (
            party.display_name
            if party
            else obj.promoter_name
            if hasattr(obj, "promoter_name")
            else (obj.promoter.name if obj.promoter else "")
        )


class ContractDetailSerializer(ContractListSerializer):
    parties = PartySerializer(many=True, read_only=True)
    terms = TermSerializer(many=True, read_only=True)
    sections = SectionSerializer(many=True, read_only=True)
    approvals = ApprovalSerializer(many=True, read_only=True)
    documents = DocumentSerializer(source="document_links", many=True, read_only=True)
    allowed_transitions = serializers.SerializerMethodField()
    execution_readiness = serializers.SerializerMethodField()
    activity = serializers.SerializerMethodField()

    class Meta(ContractListSerializer.Meta):
        fields = ContractListSerializer.Meta.fields + (
            "signed_date",
            "currency",
            "total_value",
            "governing_law",
            "jurisdiction",
            "summary",
            "internal_notes",
            "archived_at",
            "terminated_at",
            "termination_reason",
            "parties",
            "terms",
            "sections",
            "approvals",
            "documents",
            "allowed_transitions",
            "execution_readiness",
            "activity",
        )

    def get_allowed_transitions(self, obj):
        return sorted(TRANSITIONS.get(obj.status, set()))

    def get_execution_readiness(self, obj):
        errors = execution_errors(obj)
        return {"ready": not errors, "warnings": errors}

    def get_activity(self, obj):
        return self.context.get("activity", [])


class StatusSerializer(serializers.Serializer):
    to_status = serializers.ChoiceField(choices=Contract.Status.choices)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ApprovalRequestSerializer(serializers.Serializer):
    membership = serializers.PrimaryKeyRelatedField(
        queryset=ContractApproval.membership.field.related_model.objects.all()
    )


class DecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=("approved", "rejected", "cancelled"))
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class SigningSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("pending", "signed", "declined"))
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class DocumentLinkSerializer(serializers.Serializer):
    document = serializers.PrimaryKeyRelatedField(
        queryset=ContractDocument.document.field.related_model.objects.all()
    )
