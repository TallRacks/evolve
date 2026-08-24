from django.contrib import admin
from unfold.admin import ModelAdmin

from audit.services import record_event
from core.admin import PlatformSuperuserAdminMixin

from .models import (
    Booking,
    BookingContactAssignment,
    BookingStatusHistory,
    BookingTeamAssignment,
)
from .services import COMMERCIAL_FIELDS, apply_partner_snapshots, validate_transition


@admin.register(Booking)
class BookingAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "reference",
        "title",
        "organization",
        "artist",
        "event_date",
        "promoter",
        "venue",
        "status",
        "priority",
    )
    list_filter = (
        "organization",
        "artist",
        "status",
        "priority",
        "event_date",
        "promoter",
        "venue",
    )
    search_fields = (
        "reference",
        "title",
        "artist__stage_name",
        "promoter__name",
        "venue__name",
        "city_snapshot",
    )
    autocomplete_fields = ("organization", "artist", "promoter", "venue", "created_by")
    readonly_fields = ("id", "reference", "created_at", "updated_at")
    fieldsets = (
        (
            "Event",
            {
                "fields": (
                    "id",
                    "reference",
                    "title",
                    "event_date",
                    "event_start_datetime",
                    "event_end_datetime",
                    "timezone",
                )
            },
        ),
        ("Organization / Artist", {"fields": ("organization", "artist")}),
        ("Promoter / Venue", {"fields": ("promoter", "venue")}),
        ("Status / Priority", {"fields": ("status", "priority")}),
        (
            "Commercial",
            {
                "fields": (
                    "currency",
                    "performance_fee",
                    "deposit_amount",
                    "deposit_due_date",
                    "balance_due_date",
                )
            },
        ),
        ("Notes", {"fields": ("internal_notes",)}),
        (
            "Snapshots",
            {
                "fields": (
                    "promoter_name_snapshot",
                    "venue_name_snapshot",
                    "city_snapshot",
                    "country_snapshot",
                )
            },
        ),
        ("Metadata", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        previous = Booking.objects.get(pk=obj.pk) if change else None
        if previous and previous.status != obj.status:
            validate_transition(previous.status, obj.status)
        apply_partner_snapshots(
            obj,
            promoter_changed=not previous or previous.promoter_id != obj.promoter_id,
            venue_changed=not previous or previous.venue_id != obj.venue_id,
        )
        obj.full_clean()
        super().save_model(request, obj, form, change)
        action = "booking.created" if not change else "booking.updated"
        if previous and previous.status != obj.status:
            BookingStatusHistory.objects.create(
                booking=obj,
                from_status=previous.status,
                to_status=obj.status,
                changed_by=request.user,
                reason="Changed through Django admin.",
            )
            action = {
                Booking.Status.CANCELLED: "booking.cancelled",
                Booking.Status.COMPLETED: "booking.completed",
            }.get(obj.status, "booking.status_changed")
        commercial = COMMERCIAL_FIELDS.intersection(form.changed_data)
        description = f"Updated booking {obj.reference} in admin."
        if commercial:
            description += f" Commercial fields changed: {', '.join(sorted(commercial))}."
        record_event(
            actor=request.user,
            organization=obj.organization,
            action=action,
            resource=obj,
            description=description,
            request=request,
        )


@admin.register(BookingStatusHistory)
class BookingStatusHistoryAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("booking", "from_status", "to_status", "changed_by", "reason", "created_at")
    list_filter = ("from_status", "to_status", "created_at")
    search_fields = ("booking__reference", "booking__title", "changed_by__email", "reason")
    readonly_fields = (
        "id",
        "booking",
        "from_status",
        "to_status",
        "changed_by",
        "reason",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BookingTeamAssignment)
class BookingTeamAssignmentAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "booking",
        "membership",
        "responsibility",
        "is_primary",
        "is_active",
        "created_at",
    )
    list_filter = ("booking__organization", "responsibility", "is_primary", "is_active")
    search_fields = ("booking__reference", "booking__title", "membership__user__email")
    autocomplete_fields = ("booking", "membership")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        was_active = form.initial.get("is_active", True)
        obj.full_clean()
        super().save_model(request, obj, form, change)
        action = (
            "booking.team_assigned"
            if not change
            else (
                "booking.team_removed"
                if was_active and not obj.is_active
                else "booking.team_updated"
            )
        )
        record_event(
            actor=request.user,
            organization=obj.booking.organization,
            action=action,
            resource=obj.booking,
            description=f"Updated a team assignment for booking {obj.booking.reference} in admin.",
            request=request,
        )


@admin.register(BookingContactAssignment)
class BookingContactAssignmentAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "booking",
        "snapshot_name",
        "responsibility",
        "is_primary",
        "is_active",
        "created_at",
    )
    list_filter = ("booking__organization", "responsibility", "is_primary", "is_active")
    search_fields = ("booking__reference", "booking__title", "snapshot_name", "contact__email")
    autocomplete_fields = ("booking", "contact")
    readonly_fields = (
        "id",
        "snapshot_name",
        "snapshot_email",
        "snapshot_phone",
        "created_at",
        "updated_at",
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        was_active = form.initial.get("is_active", True)
        if not change:
            obj.snapshot_name = obj.contact.full_name
            obj.snapshot_email = obj.contact.email
            obj.snapshot_phone = obj.contact.phone or obj.contact.mobile
        obj.full_clean()
        super().save_model(request, obj, form, change)
        action = (
            "booking.contact_added"
            if not change
            else (
                "booking.contact_removed"
                if was_active and not obj.is_active
                else "booking.contact_updated"
            )
        )
        record_event(
            actor=request.user,
            organization=obj.booking.organization,
            action=action,
            resource=obj.booking,
            description=(
                f"Updated a contact assignment for booking {obj.booking.reference} in admin."
            ),
            request=request,
        )
