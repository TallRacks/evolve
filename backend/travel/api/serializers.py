from rest_framework import serializers

from travel.models import (
    AccommodationRoomAssignment,
    AccommodationStay,
    ItineraryTraveller,
    TravelItinerary,
    TravelSegment,
    TravelSegmentTraveller,
)
from travel.services import ITINERARY_TRANSITIONS, SEGMENT_TRANSITIONS, STAY_TRANSITIONS


class TravellerSerializer(serializers.ModelSerializer):
    artist_name = serializers.CharField(source="artist.stage_name", read_only=True)
    member_name = serializers.SerializerMethodField()

    class Meta:
        model = ItineraryTraveller
        fields = (
            "id",
            "traveller_type",
            "artist",
            "artist_name",
            "membership",
            "member_name",
            "display_name",
            "email_snapshot",
            "phone_snapshot",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_member_name(self, obj):
        if not obj.membership_id:
            return ""
        user = obj.membership.user
        return f"{user.first_name} {user.last_name}".strip() or user.email

    def to_representation(self, instance):
        value = super().to_representation(instance)
        if not self.context.get("include_private"):
            for field in ("email_snapshot", "phone_snapshot", "notes"):
                value.pop(field, None)
        return value


class SegmentTravellerSerializer(serializers.ModelSerializer):
    traveller_name = serializers.CharField(source="traveller.display_name", read_only=True)

    class Meta:
        model = TravelSegmentTraveller
        fields = ("id", "traveller", "traveller_name", "seat", "notes")
        read_only_fields = ("id",)


class SegmentSerializer(serializers.ModelSerializer):
    travellers = SegmentTravellerSerializer(
        source="traveller_assignments", many=True, read_only=True
    )
    allowed_transitions = serializers.SerializerMethodField()
    duration_minutes = serializers.SerializerMethodField()

    class Meta:
        model = TravelSegment
        fields = (
            "id",
            "segment_type",
            "sequence",
            "status",
            "provider",
            "service_number",
            "confirmation_reference",
            "departure_location",
            "arrival_location",
            "departure_at",
            "arrival_at",
            "departure_timezone",
            "arrival_timezone",
            "terminal_or_platform",
            "seat_or_vehicle_info",
            "airline",
            "flight_number",
            "departure_airport_code",
            "arrival_airport_code",
            "driver_name",
            "driver_phone",
            "notes",
            "travellers",
            "allowed_transitions",
            "duration_minutes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "status", "created_at", "updated_at")

    def get_allowed_transitions(self, obj):
        return sorted(SEGMENT_TRANSITIONS.get(obj.status, set()))

    def get_duration_minutes(self, obj):
        return (
            int((obj.arrival_at - obj.departure_at).total_seconds() / 60)
            if obj.arrival_at
            else None
        )

    def to_representation(self, instance):
        value = super().to_representation(instance)
        if not self.context.get("include_private"):
            for field in ("confirmation_reference", "driver_name", "driver_phone", "notes"):
                value.pop(field, None)
        return value


class RoomSerializer(serializers.ModelSerializer):
    traveller_name = serializers.CharField(source="traveller.display_name", read_only=True)

    class Meta:
        model = AccommodationRoomAssignment
        fields = (
            "id",
            "traveller",
            "traveller_name",
            "room_label",
            "room_type",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class StaySerializer(serializers.ModelSerializer):
    rooms = RoomSerializer(source="room_assignments", many=True, read_only=True)
    allowed_transitions = serializers.SerializerMethodField()

    class Meta:
        model = AccommodationStay
        fields = (
            "id",
            "property_name",
            "address",
            "city",
            "country",
            "timezone",
            "check_in_at",
            "check_out_at",
            "confirmation_reference",
            "contact_name",
            "contact_phone",
            "contact_email",
            "notes",
            "status",
            "sequence",
            "rooms",
            "allowed_transitions",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "status", "created_at", "updated_at")

    def get_allowed_transitions(self, obj):
        return sorted(STAY_TRANSITIONS.get(obj.status, set()))

    def to_representation(self, instance):
        value = super().to_representation(instance)
        if not self.context.get("include_private"):
            for field in (
                "confirmation_reference",
                "contact_name",
                "contact_phone",
                "contact_email",
                "notes",
            ):
                value.pop(field, None)
        return value


class ItineraryListSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    artist = serializers.SerializerMethodField()
    booking = serializers.SerializerMethodField()
    traveller_count = serializers.SerializerMethodField()
    next_segment = serializers.SerializerMethodField()

    class Meta:
        model = TravelItinerary
        fields = (
            "id",
            "organization",
            "artist",
            "booking",
            "title",
            "status",
            "starts_at",
            "ends_at",
            "timezone",
            "traveller_count",
            "next_segment",
            "created_at",
            "updated_at",
        )

    def get_organization(self, obj):
        return {"id": obj.organization_id, "name": obj.organization.name}

    def get_artist(self, obj):
        return {"id": obj.artist_id, "stage_name": obj.artist.stage_name}

    def get_booking(self, obj):
        return (
            {"id": obj.booking_id, "reference": obj.booking.reference} if obj.booking_id else None
        )

    def get_traveller_count(self, obj):
        return len([row for row in obj.travellers.all() if row.is_active])

    def get_next_segment(self, obj):
        segment = next(
            (row for row in obj.segments.all() if row.status != TravelSegment.Status.CANCELLED),
            None,
        )
        return (
            {
                "id": segment.id,
                "type": segment.segment_type,
                "departure_at": segment.departure_at,
                "destination": segment.arrival_location,
            }
            if segment
            else None
        )


class ItineraryWriteSerializer(serializers.ModelSerializer):
    artist_id = serializers.PrimaryKeyRelatedField(
        source="artist", queryset=TravelItinerary.artist.field.related_model.objects.all()
    )
    booking_id = serializers.PrimaryKeyRelatedField(
        source="booking",
        queryset=TravelItinerary.booking.field.related_model.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = TravelItinerary
        fields = (
            "title",
            "artist_id",
            "booking_id",
            "starts_at",
            "ends_at",
            "timezone",
            "purpose",
            "notes",
        )


class ItineraryDetailSerializer(ItineraryListSerializer):
    travellers = TravellerSerializer(many=True, read_only=True)
    segments = SegmentSerializer(many=True, read_only=True)
    stays = StaySerializer(many=True, read_only=True)
    allowed_transitions = serializers.SerializerMethodField()
    purpose = serializers.CharField()
    notes = serializers.CharField()
    activity = serializers.SerializerMethodField()

    class Meta(ItineraryListSerializer.Meta):
        fields = ItineraryListSerializer.Meta.fields + (
            "purpose",
            "notes",
            "travellers",
            "segments",
            "stays",
            "allowed_transitions",
            "activity",
        )

    def get_allowed_transitions(self, obj):
        return sorted(ITINERARY_TRANSITIONS.get(obj.status, set()))

    def get_activity(self, obj):
        return self.context.get("activity", [])


class StatusSerializer(serializers.Serializer):
    to_status = serializers.CharField(max_length=20)


class ReorderSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(choices=("up", "down"))


class ArtistItinerarySerializer(ItineraryListSerializer):
    segments = serializers.SerializerMethodField()
    stays = serializers.SerializerMethodField()

    class Meta(ItineraryListSerializer.Meta):
        fields = ItineraryListSerializer.Meta.fields + ("segments", "stays")

    def get_segments(self, obj):
        return [
            {
                "id": row.id,
                "type": row.segment_type,
                "provider": row.provider,
                "service_number": row.service_number,
                "departure_location": row.departure_location,
                "arrival_location": row.arrival_location,
                "departure_at": row.departure_at,
                "arrival_at": row.arrival_at,
                "departure_timezone": row.departure_timezone,
                "arrival_timezone": row.arrival_timezone,
                "status": row.status,
            }
            for row in obj.segments.all()
        ]

    def get_stays(self, obj):
        return [
            {
                "id": row.id,
                "property_name": row.property_name,
                "address": row.address,
                "city": row.city,
                "country": row.country,
                "timezone": row.timezone,
                "check_in_at": row.check_in_at,
                "check_out_at": row.check_out_at,
                "contact_name": row.contact_name,
                "contact_phone": row.contact_phone,
                "status": row.status,
            }
            for row in obj.stays.all()
        ]


class DeveloperItinerarySerializer(ArtistItinerarySerializer):
    def get_segments(self, obj):
        return [
            {
                "type": row.segment_type,
                "provider": row.provider,
                "service_number": row.service_number,
                "departure_location": row.departure_location,
                "arrival_location": row.arrival_location,
                "departure_at": row.departure_at,
                "arrival_at": row.arrival_at,
                "status": row.status,
            }
            for row in obj.segments.all()
        ]

    def get_stays(self, obj):
        return [
            {
                "property_name": row.property_name,
                "city": row.city,
                "country": row.country,
                "check_in_at": row.check_in_at,
                "check_out_at": row.check_out_at,
                "status": row.status,
            }
            for row in obj.stays.all()
        ]
