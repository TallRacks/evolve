from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from unfold.admin import ModelAdmin

from audit.services import record_event
from core.admin import PlatformSuperuserAdminMixin

from .models import (
    CallSheet,
    CallSheetAccommodationItem,
    CallSheetContactEntry,
    CallSheetScheduleItem,
    CallSheetTeamEntry,
    CallSheetTravelItem,
    CallSheetVersion,
)
from .services import cancel_version, mark_ready, publish_call_sheet_version


@admin.register(CallSheet)
class CallSheetAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "booking",
        "organization",
        "artist",
        "event_date",
        "latest_version",
        "published_version",
        "created_at",
    )
    list_filter = ("organization", "booking__status", "booking__event_date")
    search_fields = ("booking__reference", "booking__title", "booking__artist__stage_name")
    autocomplete_fields = ("organization", "booking", "created_by")
    readonly_fields = ("id", "created_at", "updated_at")

    def artist(self, obj):
        return obj.booking.artist

    def event_date(self, obj):
        return obj.booking.event_date

    def latest_version(self, obj):
        return obj.versions.order_by("-version_number").first()

    def published_version(self, obj):
        return obj.versions.filter(status=CallSheetVersion.Status.PUBLISHED).first()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            organization=obj.organization,
            action="callsheet.updated" if change else "callsheet.created",
            resource=obj,
            description=f"Updated Call Sheet for booking {obj.booking.reference} in admin.",
            request=request,
        )


@admin.register(CallSheetVersion)
class CallSheetVersionAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "call_sheet",
        "version_number",
        "status",
        "event_date",
        "venue_name",
        "published_at",
    )
    list_filter = ("call_sheet__organization", "status", "event_date")
    search_fields = ("call_sheet__booking__reference", "event_name", "artist_name", "venue_name")
    readonly_fields = (
        "id",
        "call_sheet",
        "version_number",
        "status",
        "created_by",
        "published_by",
        "published_at",
        "superseded_at",
        "created_at",
        "updated_at",
    )
    actions = ("mark_selected_ready", "publish_selected", "cancel_selected")
    fieldsets = (
        ("Identity", {"fields": ("id", "call_sheet", "version_number", "status")}),
        (
            "Event snapshot",
            {
                "fields": (
                    "title",
                    "subtitle",
                    "event_name",
                    "artist_name",
                    "event_date",
                    "event_start_datetime",
                    "event_end_datetime",
                    "timezone",
                    "promoter_name",
                )
            },
        ),
        (
            "Venue and access",
            {
                "fields": (
                    "venue_name",
                    "venue_address",
                    "city",
                    "province",
                    "country",
                    "venue_phone",
                    "access_notes",
                    "loading_access",
                    "parking_notes",
                    "backstage_access",
                    "dressing_room_notes",
                    "emergency_procedure_notes",
                )
            },
        ),
        (
            "Production",
            {
                "fields": (
                    "soundcheck_time",
                    "production_contact",
                    "stage_notes",
                    "technical_notes",
                    "backline_notes",
                    "special_requirements",
                )
            },
        ),
        (
            "Hospitality and notes",
            {
                "fields": (
                    "catering_notes",
                    "dietary_notes",
                    "guest_notes",
                    "general_notes",
                    "artist_notes",
                    "team_notes",
                    "security_notes",
                    "emergency_notes",
                )
            },
        ),
        (
            "Publication",
            {
                "fields": (
                    "created_by",
                    "published_by",
                    "published_at",
                    "superseded_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj and not obj.is_editable:
            return tuple(field.name for field in obj._meta.fields)
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        if obj.pk and not CallSheetVersion.objects.get(pk=obj.pk).is_editable:
            raise ValidationError("Published, superseded, and cancelled versions are immutable.")
        obj.full_clean()
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            organization=obj.call_sheet.organization,
            action="callsheet.updated",
            resource=obj,
            description=f"Updated Call Sheet version {obj.version_number} in admin.",
            request=request,
        )

    def _run(self, request, queryset, operation):
        for version in queryset:
            try:
                operation(actor=request.user, version=version, request=request)
            except ValidationError as error:
                self.message_user(request, "; ".join(error.messages), messages.ERROR)

    @admin.action(description="Mark selected versions ready")
    def mark_selected_ready(self, request, queryset):
        self._run(request, queryset, mark_ready)

    @admin.action(description="Publish selected versions")
    def publish_selected(self, request, queryset):
        self._run(request, queryset, publish_call_sheet_version)

    @admin.action(description="Cancel selected versions")
    def cancel_selected(self, request, queryset):
        self._run(request, queryset, cancel_version)


class ChildAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("version", "sequence", "created_at")
    list_filter = ("version__call_sheet__organization", "version__status")
    autocomplete_fields = ("version",)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (not obj or obj.version.is_editable)

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            organization=obj.version.call_sheet.organization,
            action="callsheet.child_updated",
            resource=obj.version,
            description=(
                "Updated structured entries for Call Sheet version "
                f"{obj.version.version_number} in admin."
            ),
            request=request,
        )


admin.site.register(CallSheetScheduleItem, ChildAdmin)
admin.site.register(CallSheetTeamEntry, ChildAdmin)
admin.site.register(CallSheetContactEntry, ChildAdmin)
admin.site.register(CallSheetTravelItem, ChildAdmin)
admin.site.register(CallSheetAccommodationItem, ChildAdmin)
