from django.contrib import admin

from core.admin import PlatformSuperuserAdminMixin

from .models import Tracker, TrackerSyncEvent


@admin.register(Tracker)
class TrackerAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("name", "organization", "kind", "direction", "last_sync_status", "last_synced_at")
    list_filter = ("kind", "direction", "last_sync_status")
    search_fields = ("name", "spreadsheet_id", "worksheet_name")
    readonly_fields = ("id", "created_at", "updated_at", "last_synced_at")


@admin.register(TrackerSyncEvent)
class TrackerSyncEventAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("tracker", "direction", "status", "rows_created", "rows_updated", "created_at")
    list_filter = ("direction", "status")
    search_fields = ("tracker__name", "message")
    readonly_fields = ("id", "created_at", "updated_at")
