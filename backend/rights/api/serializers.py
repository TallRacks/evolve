from decimal import Decimal

from rest_framework import serializers

from music.models import Track
from rights.models import (
    MasterRight,
    PublishingRight,
    RightsParty,
    RoyaltyAllocation,
    RoyaltyStatement,
    RoyaltySource,
    RoyaltyAdvance,
    RoyaltyStatementLine,
    TrackWork,
    Work,
    WorkContributor,
)


class PartySerializer(serializers.ModelSerializer):
    class Meta:
        model = RightsParty
        fields = (
            "id",
            "organization",
            "party_type",
            "display_name",
            "linked_artist",
            "linked_contact",
            "external_identifier",
            "email",
            "notes",
            "source_document",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization", "created_at", "updated_at")


class ContributorSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source="party.display_name", read_only=True)

    class Meta:
        model = WorkContributor
        fields = ("id", "party", "party_name", "role", "share_percentage", "sequence", "notes")


class TrackWorkSerializer(serializers.ModelSerializer):
    track_title = serializers.CharField(source="track.title", read_only=True)

    class Meta:
        model = TrackWork
        fields = ("id", "track", "track_title", "relationship_type", "created_at")


class PublishingSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source="party.display_name", read_only=True)

    class Meta:
        model = PublishingRight
        fields = (
            "id",
            "party",
            "party_name",
            "right_type",
            "ownership_percentage",
            "territory_code",
            "effective_from",
            "effective_to",
            "notes",
            "created_at",
        )


class WorkSerializer(serializers.ModelSerializer):
    track_links = TrackWorkSerializer(many=True, read_only=True)
    contributors = ContributorSerializer(many=True, read_only=True)
    publishing_rights = PublishingSerializer(many=True, read_only=True)
    publishing_total = serializers.SerializerMethodField()

    def get_publishing_total(self, obj):
        return sum((x.ownership_percentage for x in obj.publishing_rights.all()), 0)

    class Meta:
        model = Work
        fields = (
            "id",
            "organization",
            "title",
            "alternate_title",
            "status",
            "iswc",
            "internal_reference",
            "language",
            "notes",
            "publishing_total",
            "track_links",
            "contributors",
            "publishing_rights",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization", "status", "created_at", "updated_at")


class MasterSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source="party.display_name", read_only=True)
    track_title = serializers.CharField(source="track.title", read_only=True)

    class Meta:
        model = MasterRight
        fields = (
            "id",
            "organization",
            "track",
            "track_title",
            "party",
            "party_name",
            "ownership_percentage",
            "territory_code",
            "effective_from",
            "effective_to",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "organization", "created_at")


class AllocationSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source="party.display_name", read_only=True)

    class Meta:
        model = RoyaltyAllocation
        fields = ("id", "party", "party_name", "right_basis", "percentage", "amount", "created_at")


class LineSerializer(serializers.ModelSerializer):
    allocations = AllocationSerializer(many=True, read_only=True)
    allocated_amount = serializers.SerializerMethodField()

    def get_allocated_amount(self, obj):
        return sum((x.amount for x in obj.allocations.all()), 0)

    class Meta:
        model = RoyaltyStatementLine
        fields = (
            "id",
            "track",
            "release",
            "artist",
            "external_track_reference",
            "release_title",
            "upc_ean",
            "isrc",
            "territory_code",
            "platform",
            "usage_type",
            "rights_basis",
            "quantity",
            "gross_amount",
            "deductions",
            "net_amount",
            "description",
            "sequence",
            "allocated_amount",
            "allocations",
            "created_at",
        )
        read_only_fields = ("id", "net_amount", "created_at")


class RoyaltySourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoyaltySource
        fields = ("id", "organization", "name", "source_type", "is_active", "notes", "created_at", "updated_at")
        read_only_fields = ("id", "organization", "created_at", "updated_at")


class StatementSerializer(serializers.ModelSerializer):
    lines = LineSerializer(many=True, read_only=True)
    calculated_total = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    variance = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True, allow_null=True
    )

    class Meta:
        model = RoyaltyStatement
        fields = (
            "id",
            "organization",
            "statement_reference",
            "source_name",
            "source_type",
            "source",
            "status",
            "period_start",
            "period_end",
            "currency",
            "declared_total",
            "calculated_total",
            "variance",
            "source_document",
            "internal_notes",
            "finalized_at",
            "voided_at",
            "lines",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "statement_reference",
            "status",
            "finalized_at",
            "voided_at",
            "created_at",
            "updated_at",
        )


class ManualAllocationSerializer(serializers.Serializer):
    party = serializers.UUIDField()
    percentage = serializers.DecimalField(
        max_digits=7,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        max_value=Decimal("100"),
    )
    amount = serializers.DecimalField(max_digits=16, decimal_places=2, min_value=Decimal("0.01"))


class DeveloperWorkSerializer(serializers.ModelSerializer):
    recordings = serializers.SerializerMethodField()
    contributors = serializers.SerializerMethodField()

    def get_recordings(self, obj):
        return [
            {"track_id": str(x.track_id), "relationship": x.relationship_type}
            for x in obj.track_links.all()
        ]

    def get_contributors(self, obj):
        return [{"name": x.party.display_name, "role": x.role} for x in obj.contributors.all()]

    class Meta:
        model = Work
        fields = (
            "id",
            "title",
            "alternate_title",
            "status",
            "iswc",
            "language",
            "recordings",
            "contributors",
        )


class DeveloperTrackRightsSerializer(serializers.ModelSerializer):
    master_ownership = serializers.SerializerMethodField()
    works = serializers.SerializerMethodField()

    def get_master_ownership(self, obj):
        return [
            {
                "party": right.party.display_name,
                "percentage": right.ownership_percentage,
                "territory": right.territory_code,
            }
            for right in obj.master_rights.all()
        ]

    def get_works(self, obj):
        return [{"id": link.work_id, "title": link.work.title} for link in obj.work_links.all()]

    class Meta:
        model = Track
        fields = ("id", "title", "isrc", "master_ownership", "works")


class RoyaltyAdvanceSerializer(serializers.ModelSerializer):
    outstanding_amount = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)

    class Meta:
        model = RoyaltyAdvance
        fields = ("id", "organization", "source_name", "source_type", "reference", "currency", "amount", "recouped_amount", "outstanding_amount", "received_on", "notes", "created_at", "updated_at")
        read_only_fields = ("id", "organization", "outstanding_amount", "created_at", "updated_at")
