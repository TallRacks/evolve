from rest_framework import serializers

from production.models import (
    AdvanceChecklistItem,
    AdvanceRequirement,
    ProductionAdvance,
    ProductionContactAssignment,
    ProductionScheduleItem,
)
from production.services import ADVANCE_TRANSITIONS, REQUIREMENT_TRANSITIONS, SCHEDULE_TRANSITIONS


class RequirementSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(
        source="assigned_membership.user.email", read_only=True, default=""
    )
    allowed_transitions = serializers.SerializerMethodField()

    class Meta:
        model = AdvanceRequirement
        fields = (
            "id",
            "category",
            "title",
            "description",
            "status",
            "priority",
            "source",
            "response_notes",
            "due_at",
            "sequence",
            "assigned_membership",
            "assignee_name",
            "completed_at",
            "is_active",
            "allowed_transitions",
        )
        read_only_fields = ("id", "status", "completed_at", "is_active", "sequence")
        extra_kwargs = {
            "assigned_membership": {
                "queryset": (
                    AdvanceRequirement.assigned_membership.field.related_model.objects.all()
                ),
                "allow_null": True,
            }
        }

    def get_allowed_transitions(self, obj):
        return sorted(REQUIREMENT_TRANSITIONS.get(obj.status, set()))


class ContactAssignmentSerializer(serializers.ModelSerializer):
    contact_name = serializers.CharField(source="contact.full_name", read_only=True)
    contact_email = serializers.EmailField(source="contact.email", read_only=True)
    contact_phone = serializers.CharField(source="contact.phone", read_only=True)

    class Meta:
        model = ProductionContactAssignment
        fields = (
            "id",
            "contact",
            "contact_name",
            "contact_email",
            "contact_phone",
            "role",
            "responsibility",
            "is_primary",
            "is_active",
            "notes",
        )
        read_only_fields = ("id", "is_active")
        extra_kwargs = {
            "contact": {
                "queryset": ProductionContactAssignment.contact.field.related_model.objects.all()
            }
        }


class ScheduleSerializer(serializers.ModelSerializer):
    allowed_transitions = serializers.SerializerMethodField()

    class Meta:
        model = ProductionScheduleItem
        fields = (
            "id",
            "title",
            "item_type",
            "starts_at",
            "ends_at",
            "timezone",
            "location",
            "notes",
            "sequence",
            "status",
            "is_active",
            "allowed_transitions",
        )
        read_only_fields = ("id", "status", "is_active", "sequence")

    def get_allowed_transitions(self, obj):
        return sorted(SCHEDULE_TRANSITIONS.get(obj.status, set()))


class ChecklistSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(
        source="assigned_membership.user.email", read_only=True, default=""
    )
    completed_by_name = serializers.CharField(
        source="completed_by.email", read_only=True, default=""
    )

    class Meta:
        model = AdvanceChecklistItem
        fields = (
            "id",
            "title",
            "category",
            "is_completed",
            "completed_by_name",
            "completed_at",
            "assigned_membership",
            "assignee_name",
            "due_at",
            "sequence",
            "notes",
            "is_active",
        )
        read_only_fields = (
            "id",
            "is_completed",
            "completed_by_name",
            "completed_at",
            "is_active",
            "sequence",
        )
        extra_kwargs = {
            "assigned_membership": {
                "queryset": (
                    AdvanceChecklistItem.assigned_membership.field.related_model.objects.all()
                ),
                "allow_null": True,
            }
        }


class AdvanceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionAdvance
        fields = (
            "booking",
            "venue",
            "promoter",
            "production_title",
            "production_notes",
            "access_notes",
            "parking_notes",
            "security_notes",
            "advance_due_at",
        )
        extra_kwargs = {
            "booking": {"queryset": ProductionAdvance.booking.field.related_model.objects.all()},
            "venue": {
                "queryset": ProductionAdvance.venue.field.related_model.objects.all(),
                "allow_null": True,
            },
            "promoter": {
                "queryset": ProductionAdvance.promoter.field.related_model.objects.all(),
                "allow_null": True,
            },
        }


class AdvanceListSerializer(serializers.ModelSerializer):
    artist_name = serializers.CharField(source="artist.stage_name", read_only=True)
    booking_reference = serializers.CharField(source="booking.reference", read_only=True)
    show_date = serializers.DateField(source="booking.event_date", read_only=True)
    venue_name = serializers.CharField(source="venue.name", read_only=True, default="")
    requirement_progress = serializers.SerializerMethodField()
    checklist_progress = serializers.SerializerMethodField()
    blocked_requirements = serializers.SerializerMethodField()
    next_schedule_item = serializers.SerializerMethodField()

    class Meta:
        model = ProductionAdvance
        fields = (
            "id",
            "organization",
            "production_title",
            "artist",
            "artist_name",
            "booking",
            "booking_reference",
            "show_date",
            "venue",
            "venue_name",
            "promoter",
            "status",
            "advance_due_at",
            "requirement_progress",
            "checklist_progress",
            "blocked_requirements",
            "next_schedule_item",
        )

    def get_requirement_progress(self, obj):
        rows = [x for x in obj.requirements.all() if x.is_active]
        done = sum(x.status in {"confirmed", "not_applicable"} for x in rows)
        return {"complete": done, "total": len(rows)}

    def get_checklist_progress(self, obj):
        rows = [x for x in obj.checklist_items.all() if x.is_active]
        return {"complete": sum(x.is_completed for x in rows), "total": len(rows)}

    def get_blocked_requirements(self, obj):
        return sum(x.is_active and x.status == "blocked" for x in obj.requirements.all())

    def get_next_schedule_item(self, obj):
        rows = [x for x in obj.schedule_items.all() if x.is_active and x.status != "cancelled"]
        if not rows:
            return None
        row = sorted(rows, key=lambda x: x.starts_at)[0]
        return {
            "id": row.id,
            "title": row.title,
            "starts_at": row.starts_at,
            "timezone": row.timezone,
        }


class AdvanceDetailSerializer(AdvanceListSerializer):
    requirements = RequirementSerializer(many=True, read_only=True)
    contact_assignments = ContactAssignmentSerializer(many=True, read_only=True)
    schedule_items = ScheduleSerializer(many=True, read_only=True)
    checklist_items = ChecklistSerializer(many=True, read_only=True)
    allowed_transitions = serializers.SerializerMethodField()
    activity = serializers.SerializerMethodField()
    travel = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    call_sheet = serializers.SerializerMethodField()

    class Meta(AdvanceListSerializer.Meta):
        fields = AdvanceListSerializer.Meta.fields + (
            "production_notes",
            "access_notes",
            "parking_notes",
            "security_notes",
            "last_advanced_at",
            "requirements",
            "contact_assignments",
            "schedule_items",
            "checklist_items",
            "allowed_transitions",
            "activity",
            "travel",
            "documents",
            "call_sheet",
        )

    def get_allowed_transitions(self, obj):
        return sorted(ADVANCE_TRANSITIONS.get(obj.status, set()))

    def get_activity(self, obj):
        return self.context.get("activity", [])

    def get_travel(self, obj):
        from travel.models import TravelItinerary

        item = TravelItinerary.objects.filter(booking=obj.booking).first()
        if not item:
            return None
        return {"id": item.id, "title": item.title, "status": item.status}

    def get_documents(self, obj):
        return [
            {
                "id": x.document_id,
                "title": x.document.title,
                "external_url": x.document.external_url,
                "link_id": x.id,
            }
            for x in obj.document_links.select_related("document")
        ]

    def get_call_sheet(self, obj):
        from callsheets.models import CallSheet

        sheet = CallSheet.objects.filter(booking=obj.booking).first()
        if not sheet:
            return None
        version = sheet.versions.order_by("-version_number").first()
        return {
            "id": sheet.id,
            "version_id": version.id if version else None,
            "status": version.status if version else None,
        }


class ArtistAdvanceSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="production_title")
    booking_reference = serializers.CharField(source="booking.reference")
    show_date = serializers.DateField(source="booking.event_date")
    venue_name = serializers.CharField(source="venue.name", default="")
    schedule = serializers.SerializerMethodField()
    contacts = serializers.SerializerMethodField()
    requirements = serializers.SerializerMethodField()

    class Meta:
        model = ProductionAdvance
        fields = (
            "id",
            "title",
            "booking_reference",
            "show_date",
            "venue_name",
            "status",
            "schedule",
            "contacts",
            "requirements",
        )

    def get_schedule(self, obj):
        return [
            {
                "id": x.id,
                "title": x.title,
                "item_type": x.item_type,
                "starts_at": x.starts_at,
                "ends_at": x.ends_at,
                "timezone": x.timezone,
                "location": x.location,
                "status": x.status,
            }
            for x in obj.schedule_items.all()
            if x.is_active and x.status != "cancelled"
        ]

    def get_contacts(self, obj):
        return [
            {
                "id": x.id,
                "name": x.contact.full_name,
                "role": x.role,
                "responsibility": x.responsibility,
            }
            for x in obj.contact_assignments.all()
            if x.is_active and x.is_primary
        ]

    def get_requirements(self, obj):
        return [
            {"id": x.id, "category": x.category, "title": x.title, "status": x.status}
            for x in obj.requirements.all()
            if x.is_active and x.source == "artist"
        ]


class DeveloperAdvanceSerializer(serializers.ModelSerializer):
    artist = serializers.CharField(source="artist.stage_name")
    booking_reference = serializers.CharField(source="booking.reference")
    venue = serializers.CharField(source="venue.name", default="")
    show_date = serializers.DateField(source="booking.event_date")
    requirement_summary = serializers.SerializerMethodField()
    schedule_summary = serializers.SerializerMethodField()

    class Meta:
        model = ProductionAdvance
        fields = (
            "id",
            "production_title",
            "artist",
            "booking_reference",
            "venue",
            "status",
            "show_date",
            "requirement_summary",
            "schedule_summary",
        )

    def get_requirement_summary(self, obj):
        rows = [x for x in obj.requirements.all() if x.is_active]
        return {
            "total": len(rows),
            "confirmed": sum(x.status in {"confirmed", "not_applicable"} for x in rows),
            "blocked": sum(x.status == "blocked" for x in rows),
        }

    def get_schedule_summary(self, obj):
        return [
            {
                "title": x.title,
                "item_type": x.item_type,
                "starts_at": x.starts_at,
                "timezone": x.timezone,
                "status": x.status,
            }
            for x in obj.schedule_items.all()
            if x.is_active
        ]


class StatusSerializer(serializers.Serializer):
    to_status = serializers.CharField(max_length=30)


class ReorderSerializer(serializers.Serializer):
    direction = serializers.ChoiceField(choices=("up", "down"))
