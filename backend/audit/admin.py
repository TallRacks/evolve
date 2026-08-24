from django.contrib import admin
from unfold.admin import ModelAdmin

from core.admin import PlatformSuperuserAdminMixin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "created_at",
        "action",
        "actor",
        "organization",
        "resource_type",
        "resource_id",
    )
    list_filter = ("action", "resource_type", "organization")
    search_fields = ("action", "description", "actor__email", "resource_id")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 50
    readonly_fields = (
        "id",
        "created_at",
        "actor",
        "organization",
        "action",
        "resource_type",
        "resource_id",
        "description",
        "ip_address",
    )
    fieldsets = (
        ("Event", {"fields": ("id", "created_at", "action", "description")}),
        ("Context", {"fields": ("actor", "organization", "ip_address")}),
        ("Resource", {"fields": ("resource_type", "resource_id")}),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
