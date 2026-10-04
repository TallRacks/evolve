from rest_framework import serializers

from callsheets.models import (
    CallSheet,
    CallSheetAccommodationItem,
    CallSheetContactEntry,
    CallSheetScheduleItem,
    CallSheetTeamEntry,
    CallSheetTravelItem,
    CallSheetVersion,
)
from white_label.services import effective_branding


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallSheetScheduleItem
        exclude = ("version",)
        read_only_fields = ("id", "created_at", "updated_at")


class TeamSerializer(serializers.ModelSerializer):
    membership_id = serializers.UUIDField(required=False, allow_null=True)
    booking_team_assignment_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = CallSheetTeamEntry
        exclude = ("version", "membership", "booking_team_assignment")
        read_only_fields = ("id", "created_at", "updated_at")


class ContactSerializer(serializers.ModelSerializer):
    source_contact_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = CallSheetContactEntry
        exclude = ("version", "source_contact")
        read_only_fields = ("id", "created_at", "updated_at")


class TravelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallSheetTravelItem
        exclude = ("version",)
        read_only_fields = ("id", "created_at", "updated_at")


class AccommodationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallSheetAccommodationItem
        exclude = ("version",)
        read_only_fields = ("id", "created_at", "updated_at")


VERSION_EDIT_FIELDS = (
    "title",
    "subtitle",
    "event_name",
    "artist_name",
    "event_date",
    "event_start_datetime",
    "event_end_datetime",
    "timezone",
    "venue_name",
    "venue_address",
    "city",
    "province",
    "country",
    "venue_phone",
    "promoter_name",
    "promoter_contact_details",
    "point_of_contact",
    "point_of_contact_details",
    "onsite_contact",
    "onsite_contact_details",
    "performance_length_minutes",
    "transportation_mode",
    "meet_up_point",
    "meet_up_address",
    "meet_up_url",
    "call_time",
    "emergency_contact",
    "nearest_police_station",
    "nearest_hospital",
    "nearest_fueling_station",
    "access_notes",
    "loading_access",
    "parking_notes",
    "backstage_access",
    "dressing_room_notes",
    "emergency_procedure_notes",
    "soundcheck_time",
    "production_contact",
    "stage_notes",
    "technical_notes",
    "backline_notes",
    "special_requirements",
    "catering_notes",
    "dietary_notes",
    "guest_notes",
    "general_notes",
    "artist_notes",
    "team_notes",
    "security_notes",
    "emergency_notes",
)


class VersionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallSheetVersion
        fields = VERSION_EDIT_FIELDS


class VersionSerializer(serializers.ModelSerializer):
    booking = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()
    branding = serializers.SerializerMethodField()
    published_by = serializers.EmailField(source="published_by.email", allow_null=True)
    created_by = serializers.EmailField(source="created_by.email", allow_null=True)
    schedule = ScheduleSerializer(source="schedule_items", many=True, read_only=True)
    team = TeamSerializer(source="team_entries", many=True, read_only=True)
    contacts = ContactSerializer(source="contact_entries", many=True, read_only=True)
    travel = TravelSerializer(source="travel_items", many=True, read_only=True)
    accommodation = AccommodationSerializer(source="accommodation_items", many=True, read_only=True)

    class Meta:
        model = CallSheetVersion
        fields = (
            "id",
            "call_sheet_id",
            "version_number",
            "status",
            "created_at",
            "updated_at",
            "created_by",
            "published_by",
            "published_at",
            "superseded_at",
            "booking",
            "organization",
            "branding",
            *VERSION_EDIT_FIELDS,
            "schedule",
            "team",
            "contacts",
            "travel",
            "accommodation",
        )

    def get_booking(self, version):
        booking = version.call_sheet.booking
        return {"id": booking.id, "reference": booking.reference, "title": booking.title}

    def get_organization(self, version):
        organization = version.call_sheet.organization
        return {"id": organization.id, "name": organization.name}

    def get_branding(self, version):
        return effective_branding(version.call_sheet.organization)


class VersionSummarySerializer(serializers.ModelSerializer):
    created_by = serializers.EmailField(source="created_by.email", allow_null=True)
    published_by = serializers.EmailField(source="published_by.email", allow_null=True)

    class Meta:
        model = CallSheetVersion
        fields = (
            "id",
            "version_number",
            "status",
            "title",
            "event_date",
            "venue_name",
            "published_at",
            "created_at",
            "updated_at",
            "created_by",
            "published_by",
        )


class CallSheetSerializer(serializers.ModelSerializer):
    booking = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()
    versions = VersionSummarySerializer(many=True, read_only=True)

    class Meta:
        model = CallSheet
        fields = ("id", "organization", "booking", "versions", "created_at", "updated_at")

    def get_booking(self, call_sheet):
        booking = call_sheet.booking
        return {
            "id": booking.id,
            "reference": booking.reference,
            "title": booking.title,
            "artist": booking.artist.stage_name,
            "event_date": booking.event_date,
        }

    def get_organization(self, call_sheet):
        return {"id": call_sheet.organization_id, "name": call_sheet.organization.name}


class VersionCreateSerializer(serializers.Serializer):
    source_version_id = serializers.UUIDField(required=False, allow_null=True)


class DeveloperCallSheetSerializer(serializers.ModelSerializer):
    call_sheet_id = serializers.UUIDField()
    booking_reference = serializers.CharField(source="call_sheet.booking.reference")
    artist = serializers.CharField(source="artist_name")
    event = serializers.CharField(source="event_name")
    date = serializers.DateField(source="event_date")
    venue = serializers.CharField(source="venue_name")
    version = serializers.IntegerField(source="version_number")

    class Meta:
        model = CallSheetVersion
        fields = (
            "call_sheet_id",
            "id",
            "version",
            "booking_reference",
            "artist",
            "event",
            "date",
            "venue",
            "status",
            "published_at",
        )
