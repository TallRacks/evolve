from django.contrib import admin
from unfold.admin import ModelAdmin

from audit.services import record_event
from core.admin import PlatformSuperuserAdminMixin

from .models import CalendarEvent
from .services import transition_event


@admin.register(CalendarEvent)
class CalendarEventAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "title",
        "organization",
        "artist",
        "event_type",
        "starts_at",
        "ends_at",
        "visibility",
        "status",
    )
    list_filter = ("organization", "event_type", "visibility", "status", "starts_at")
    search_fields = ("title", "description", "location")
    readonly_fields = ("status", "created_by", "created_at", "updated_at")
    actions = ("cancel_events", "archive_events")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            organization=obj.organization,
            action="calendar.event_updated" if change else "calendar.event_created",
            resource=obj,
            description="Calendar event saved in administration.",
            request=request,
        )

    @admin.action(description="Cancel selected events")
    def cancel_events(self, request, queryset):
        for obj in queryset:
            transition_event(
                obj, CalendarEvent.Status.CANCELLED, actor=request.user, request=request
            )

    @admin.action(description="Archive selected events")
    def archive_events(self, request, queryset):
        for obj in queryset:
            transition_event(
                obj, CalendarEvent.Status.ARCHIVED, actor=request.user, request=request
            )
