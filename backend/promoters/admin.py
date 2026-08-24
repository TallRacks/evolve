from django.contrib import admin
from unfold.admin import ModelAdmin

from audit.services import record_event
from core.admin import PlatformSuperuserAdminMixin

from .models import Promoter, PromoterContact


@admin.register(Promoter)
class PromoterAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("name", "organization", "city", "country", "status", "created_at")
    list_filter = ("organization", "status", "country")
    search_fields = ("name", "company_name", "email", "city")
    autocomplete_fields = ("organization",)
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        ("Identity", {"fields": ("id", "organization", "name", "company_name", "slug")}),
        ("Contact", {"fields": ("email", "phone", "website")}),
        (
            "Location",
            {
                "fields": (
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "province",
                    "postal_code",
                    "country",
                )
            },
        ),
        ("Status", {"fields": ("status",)}),
        ("Notes", {"fields": ("notes",)}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        previous = form.initial.get("status")
        super().save_model(request, obj, form, change)
        action = "promoter.created" if not change else "promoter.updated"
        if change and previous != obj.status:
            action = (
                "promoter.reactivated"
                if obj.status == Promoter.Status.ACTIVE
                else "promoter.deactivated"
            )
        record_event(
            actor=request.user,
            organization=obj.organization,
            action=action,
            resource=obj,
            description=f"Updated promoter {obj.name} in admin.",
            request=request,
        )


@admin.register(PromoterContact)
class PromoterContactAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "promoter",
        "contact",
        "responsibility",
        "is_primary",
        "is_active",
        "created_at",
    )
    list_filter = ("promoter__organization", "responsibility", "is_primary", "is_active")
    search_fields = (
        "promoter__name",
        "contact__first_name",
        "contact__last_name",
        "contact__email",
    )
    autocomplete_fields = ("promoter", "contact")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        was_active = form.initial.get("is_active", True)
        super().save_model(request, obj, form, change)
        action = (
            "promoter.contact_added"
            if not change
            else (
                "promoter.contact_removed"
                if was_active and not obj.is_active
                else "promoter.contact_updated"
            )
        )
        record_event(
            actor=request.user,
            organization=obj.promoter.organization,
            action=action,
            resource=obj.promoter,
            description=f"Updated a contact relationship for {obj.promoter.name} in admin.",
            request=request,
        )
