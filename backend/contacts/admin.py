from django.contrib import admin
from unfold.admin import ModelAdmin

from audit.services import record_event
from core.admin import PlatformSuperuserAdminMixin

from .models import Contact


@admin.register(Contact)
class ContactAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "full_name",
        "organization",
        "job_title",
        "email",
        "phone",
        "is_active",
        "created_at",
    )
    list_filter = ("organization", "is_active")
    search_fields = ("first_name", "last_name", "email", "phone", "mobile", "job_title")
    autocomplete_fields = ("organization",)
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        ("Identity", {"fields": ("id", "organization", "first_name", "last_name", "job_title")}),
        ("Contact", {"fields": ("email", "phone", "mobile")}),
        ("Status", {"fields": ("is_active",)}),
        ("Notes", {"fields": ("notes",)}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        was_active = form.initial.get("is_active", True)
        super().save_model(request, obj, form, change)
        action = (
            "contact.created"
            if not change
            else ("contact.deactivated" if was_active and not obj.is_active else "contact.updated")
        )
        record_event(
            actor=request.user,
            organization=obj.organization,
            action=action,
            resource=obj,
            description="Updated a business contact in admin.",
            request=request,
        )
