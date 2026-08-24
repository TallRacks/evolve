from rest_framework import serializers

from bookings.models import (
    Booking,
    BookingContactAssignment,
    BookingStatusHistory,
    BookingTeamAssignment,
)


class BookingListSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    artist = serializers.SerializerMethodField()
    promoter = serializers.SerializerMethodField()
    venue = serializers.SerializerMethodField()
    primary_assignment = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = (
            "id",
            "reference",
            "organization",
            "title",
            "artist",
            "promoter",
            "venue",
            "status",
            "priority",
            "event_date",
            "event_start_datetime",
            "event_end_datetime",
            "timezone",
            "venue_name_snapshot",
            "city_snapshot",
            "country_snapshot",
            "promoter_name_snapshot",
            "primary_assignment",
            "created_at",
            "updated_at",
        )

    def get_organization(self, booking):
        return {"id": booking.organization_id, "name": booking.organization.name}

    def get_artist(self, booking):
        return {"id": booking.artist_id, "stage_name": booking.artist.stage_name}

    def get_promoter(self, booking):
        return (
            None
            if not booking.promoter
            else {"id": booking.promoter_id, "name": booking.promoter.name}
        )

    def get_venue(self, booking):
        return None if not booking.venue else {"id": booking.venue_id, "name": booking.venue.name}

    def get_primary_assignment(self, booking):
        assignment = (
            booking.team_assignments.filter(is_active=True, is_primary=True)
            .select_related("membership__user")
            .first()
        )
        if not assignment:
            return None
        user = assignment.membership.user
        return {
            "name": f"{user.first_name} {user.last_name}".strip() or user.email,
            "responsibility": assignment.responsibility,
        }


class BookingDetailSerializer(BookingListSerializer):
    contacts = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()
    status_history = serializers.SerializerMethodField()
    activity = serializers.SerializerMethodField()
    allowed_transitions = serializers.SerializerMethodField()

    class Meta(BookingListSerializer.Meta):
        fields = BookingListSerializer.Meta.fields + (
            "internal_notes",
            "contacts",
            "team",
            "status_history",
            "activity",
            "allowed_transitions",
        )

    def get_fields(self):
        fields = super().get_fields()
        if self.context.get("include_commercial"):
            fields.update(
                {
                    "currency": serializers.CharField(read_only=True),
                    "performance_fee": serializers.DecimalField(
                        max_digits=14, decimal_places=2, read_only=True
                    ),
                    "deposit_amount": serializers.DecimalField(
                        max_digits=14, decimal_places=2, read_only=True
                    ),
                    "deposit_due_date": serializers.DateField(read_only=True),
                    "balance_due_date": serializers.DateField(read_only=True),
                }
            )
        return fields

    def get_contacts(self, booking):
        return BookingContactAssignmentSerializer(
            booking.contact_assignments.select_related("contact"), many=True
        ).data

    def get_team(self, booking):
        return BookingTeamAssignmentSerializer(
            booking.team_assignments.select_related("membership__user"), many=True
        ).data

    def get_status_history(self, booking):
        return BookingStatusHistorySerializer(
            booking.status_history.select_related("changed_by"), many=True
        ).data

    def get_activity(self, booking):
        return self.context.get("activity", [])

    def get_allowed_transitions(self, booking):
        return self.context.get("allowed_transitions", [])


class BookingWriteSerializer(serializers.ModelSerializer):
    artist_id = serializers.PrimaryKeyRelatedField(
        source="artist", queryset=Booking.artist.field.related_model.objects.all()
    )
    promoter_id = serializers.PrimaryKeyRelatedField(
        source="promoter",
        queryset=Booking.promoter.field.related_model.objects.all(),
        required=False,
        allow_null=True,
    )
    venue_id = serializers.PrimaryKeyRelatedField(
        source="venue",
        queryset=Booking.venue.field.related_model.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Booking
        fields = (
            "title",
            "artist_id",
            "promoter_id",
            "venue_id",
            "priority",
            "event_date",
            "event_start_datetime",
            "event_end_datetime",
            "timezone",
            "currency",
            "performance_fee",
            "deposit_amount",
            "deposit_due_date",
            "balance_due_date",
            "internal_notes",
        )


class BookingCreateSerializer(BookingWriteSerializer):
    class Meta(BookingWriteSerializer.Meta):
        fields = BookingWriteSerializer.Meta.fields + ("status",)


class StatusTransitionSerializer(serializers.Serializer):
    to_status = serializers.ChoiceField(choices=Booking.Status.choices)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class BookingStatusHistorySerializer(serializers.ModelSerializer):
    changed_by = serializers.EmailField(source="changed_by.email", allow_null=True)

    class Meta:
        model = BookingStatusHistory
        fields = ("id", "from_status", "to_status", "changed_by", "reason", "created_at")


class BookingTeamAssignmentSerializer(serializers.ModelSerializer):
    member = serializers.SerializerMethodField()

    class Meta:
        model = BookingTeamAssignment
        fields = (
            "id",
            "member",
            "responsibility",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "member", "created_at", "updated_at")

    def get_member(self, assignment):
        membership = assignment.membership
        user = membership.user
        return {
            "membership_id": membership.id,
            "user_id": user.id,
            "email": user.email,
            "name": f"{user.first_name} {user.last_name}".strip() or user.email,
            "organization_role": membership.role,
            "membership_active": membership.is_active,
        }


class BookingTeamCreateSerializer(serializers.Serializer):
    membership_id = serializers.UUIDField()
    responsibility = serializers.ChoiceField(choices=BookingTeamAssignment.Responsibility.choices)
    is_primary = serializers.BooleanField(default=False)


class BookingContactAssignmentSerializer(serializers.ModelSerializer):
    contact_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = BookingContactAssignment
        fields = (
            "id",
            "contact_id",
            "responsibility",
            "is_primary",
            "is_active",
            "snapshot_name",
            "snapshot_email",
            "snapshot_phone",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "contact_id",
            "snapshot_name",
            "snapshot_email",
            "snapshot_phone",
            "created_at",
            "updated_at",
        )


class BookingContactCreateSerializer(serializers.Serializer):
    contact_id = serializers.UUIDField()
    responsibility = serializers.ChoiceField(
        choices=BookingContactAssignment.Responsibility.choices
    )
    is_primary = serializers.BooleanField(default=False)


class DeveloperBookingSerializer(serializers.ModelSerializer):
    artist = serializers.CharField(source="artist.stage_name")
    promoter = serializers.CharField(source="promoter_name_snapshot")
    venue = serializers.CharField(source="venue_name_snapshot")
    city = serializers.CharField(source="city_snapshot")
    country = serializers.CharField(source="country_snapshot")

    class Meta:
        model = Booking
        fields = (
            "id",
            "reference",
            "title",
            "artist",
            "event_date",
            "event_start_datetime",
            "timezone",
            "status",
            "priority",
            "promoter",
            "venue",
            "city",
            "country",
            "updated_at",
        )
