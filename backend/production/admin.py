from django.contrib import admin
from unfold.admin import ModelAdmin

from core.admin import PlatformSuperuserAdminMixin

from .models import (
    AdvanceChecklistItem,
    AdvanceRequirement,
    ProductionAdvance,
    ProductionContactAssignment,
    ProductionScheduleItem,
)


class SafeAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProductionAdvance)
class ProductionAdvanceAdmin(SafeAdmin):
    list_display = (
        "production_title",
        "organization",
        "artist",
        "booking",
        "venue",
        "status",
        "advance_due_at",
        "updated_at",
    )
    list_filter = ("organization", "status", "artist", "venue")
    search_fields = (
        "production_title",
        "artist__stage_name",
        "booking__reference",
        "venue__name",
        "promoter__name",
    )
    readonly_fields = ("status", "archived_at", "last_advanced_at", "created_at", "updated_at")
    fieldsets = (
        ("Identity", {"fields": ("organization", "production_title")}),
        ("Booking / Artist", {"fields": ("booking", "artist")}),
        ("Venue / Promoter", {"fields": ("venue", "promoter")}),
        (
            "Advance status",
            {"fields": ("status", "advance_due_at", "last_advanced_at", "archived_at")},
        ),
        (
            "Operations",
            {"fields": ("production_notes", "access_notes", "parking_notes", "security_notes")},
        ),
        ("Metadata", {"fields": ("created_by", "created_at", "updated_at")}),
    )


@admin.register(AdvanceRequirement)
class RequirementAdmin(SafeAdmin):
    list_display = (
        "advance",
        "category",
        "title",
        "priority",
        "status",
        "assigned_membership",
        "due_at",
    )
    list_filter = ("advance__organization", "category", "status", "priority")
    search_fields = ("advance__production_title", "title")
    readonly_fields = ("status", "completed_at", "sequence")


@admin.register(ProductionScheduleItem)
class ScheduleAdmin(SafeAdmin):
    list_display = ("advance", "item_type", "title", "starts_at", "timezone", "status")
    list_filter = ("advance__organization", "item_type", "status")
    readonly_fields = ("status", "sequence")


@admin.register(AdvanceChecklistItem)
class ChecklistAdmin(SafeAdmin):
    list_display = ("advance", "title", "category", "assigned_membership", "due_at", "is_completed")
    list_filter = ("advance__organization", "category", "is_completed")
    readonly_fields = ("is_completed", "completed_by", "completed_at", "sequence")


@admin.register(ProductionContactAssignment)
class ContactAdmin(SafeAdmin):
    list_display = ("advance", "contact", "role", "is_primary", "is_active")
    list_filter = ("advance__organization", "role", "is_primary", "is_active")
