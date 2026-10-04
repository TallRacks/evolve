from rest_framework import serializers

from bookings.models import (
    Booking,
    BookingOption,
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
    days_out = serializers.SerializerMethodField()
    readiness = serializers.SerializerMethodField()
    next_action = serializers.SerializerMethodField()

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
            "performance_type",
            "event_type",
            "event_date",
            "event_start_datetime",
            "event_end_datetime",
            "timezone",
            "venue_name_snapshot",
            "city_snapshot",
            "country_snapshot",
            "promoter_name_snapshot",
            "primary_assignment",
            "days_out",
            "readiness",
            "next_action",
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

    def get_days_out(self, booking):
        from django.utils import timezone

        return (booking.event_date - timezone.localdate()).days

    def get_readiness(self, booking):
        production = getattr(booking, "production_advance", None)
        travel = getattr(booking, "travel_itinerary", None)
        call_sheet = getattr(booking, "call_sheet", None)
        latest_version = call_sheet.versions.first() if call_sheet else None
        items = {
            "production": {
                "status": production.status if production else "missing",
                "href": f"/workspace/production/{production.id}"
                if production
                else f"/workspace/production/new?booking={booking.id}",
            },
            "travel": {
                "status": travel.status if travel else "missing",
                "href": f"/workspace/travel/{travel.id}"
                if travel
                else f"/workspace/travel/new?booking={booking.id}",
            },
            "call_sheet": {
                "status": latest_version.status if latest_version else "missing",
                "href": f"/workspace/call-sheets/{latest_version.id}"
                if latest_version
                else f"/workspace/bookings/{booking.id}/call-sheet",
            },
        }
        if self.context.get("include_contracts"):
            contract = booking.contracts.first()
            items["contract"] = {
                "status": contract.status if contract else "missing",
                "href": f"/workspace/contracts/{contract.id}"
                if contract
                else f"/workspace/contracts/new?booking={booking.id}",
            }
        if self.context.get("include_finance"):
            invoice = booking.invoices.first()
            items["invoice"] = {
                "status": invoice.status if invoice else "missing",
                "href": f"/workspace/finance/invoices/{invoice.id}"
                if invoice
                else f"/workspace/finance/invoices/new?booking={booking.id}",
            }
        return items

    def get_next_action(self, booking):
        """Return a deterministic action for the booking command centre."""
        production = getattr(booking, "production_advance", None)
        travel = getattr(booking, "travel_itinerary", None)
        call_sheet = getattr(booking, "call_sheet", None)
        latest_version = call_sheet.versions.first() if call_sheet else None
        booking_href = f"/workspace/bookings/{booking.id}"
        if not booking.venue and not booking.city_snapshot:
            return {
                "key": "complete_venue",
                "label": "Complete venue or city",
                "href": f"{booking_href}/edit",
            }
        if not production:
            return {
                "key": "create_production",
                "label": "Start Production Advance",
                "href": f"/workspace/production/new?booking={booking.id}",
            }
        if not latest_version:
            return {
                "key": "generate_call_sheet",
                "label": "Generate Call Sheet",
                "href": f"{booking_href}/call-sheet",
            }
        if latest_version.status == "draft":
            return {
                "key": "review_call_sheet",
                "label": "Review Call Sheet",
                "href": f"/workspace/call-sheets/{latest_version.id}",
            }
        if travel is None and booking.event_start_datetime:
            return {
                "key": "complete_travel",
                "label": "Complete Travel",
                "href": f"/workspace/travel/new?booking={booking.id}",
            }
        if self.context.get("include_contracts") and not booking.contracts.first():
            return {
                "key": "review_contract",
                "label": "Review Contract",
                "href": f"/workspace/contracts/new?booking={booking.id}",
            }
        return {
            "key": "review_readiness",
            "label": "Review booking readiness",
            "href": booking_href,
        }

    def get_primary_assignment(self, booking):
        assignment = next(
            (item for item in booking.team_assignments.all() if item.is_active and item.is_primary),
            None,
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
            "custom_fields",
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
            "performance_type",
            "event_type",
            "event_date",
            "event_start_datetime",
            "event_end_datetime",
            "timezone",
            "city_snapshot",
            "currency",
            "performance_fee",
            "deposit_amount",
            "deposit_due_date",
            "balance_due_date",
            "internal_notes",
            "custom_fields",
        )


class BookingCreateSerializer(BookingWriteSerializer):
    prepare_production = serializers.BooleanField(default=True, write_only=True)
    prepare_call_sheet = serializers.BooleanField(default=True, write_only=True)
    prepare_travel = serializers.BooleanField(default=False, write_only=True)
    initial_membership_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    initial_contact_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)

    class Meta(BookingWriteSerializer.Meta):
        fields = BookingWriteSerializer.Meta.fields + (
            "status",
            "prepare_production",
            "prepare_call_sheet",
            "prepare_travel",
            "initial_membership_id",
            "initial_contact_id",
        )


class BookingSetupSerializer(serializers.Serializer):
    create_production = serializers.BooleanField(default=False)
    create_call_sheet = serializers.BooleanField(default=False)
    create_travel = serializers.BooleanField(default=False)


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


class BookingOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingOption
        fields = ("id", "organization", "category", "name", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "organization", "created_at", "updated_at")
