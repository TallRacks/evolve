from django.contrib import admin
from unfold.admin import ModelAdmin

from audit.services import record_event
from core.admin import PlatformSuperuserAdminMixin

from .models import Venue, VenueContact


@admin.register(Venue)
class VenueAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("name", "organization", "city", "country", "capacity", "status", "created_at")
    list_filter = ("organization", "status", "country")
    search_fields = ("name", "city", "address_line_1")
    autocomplete_fields = ("organization",)
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        ("Identity", {"fields": ("id", "organization", "name", "slug")}),
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
                    "latitude",
                    "longitude",
                )
            },
        ),
        ("Contact", {"fields": ("public_email", "public_phone", "website")}),
        ("Operations", {"fields": ("capacity", "timezone")}),
        ("Status", {"fields": ("status",)}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        previous = form.initial.get("status")
        super().save_model(request, obj, form, change)
        action = "venue.created" if not change else "venue.updated"
        if change and previous != obj.status:
            action = (
                "venue.reactivated" if obj.status == Venue.Status.ACTIVE else "venue.deactivated"
            )
        record_event(
            actor=request.user,
            organization=obj.organization,
            action=action,
            resource=obj,
            description=f"Updated venue {obj.name} in admin.",
            request=request,
        )


@admin.register(VenueContact)
class VenueContactAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("venue", "contact", "responsibility", "is_primary", "is_active", "created_at")
    list_filter = ("venue__organization", "responsibility", "is_primary", "is_active")
    search_fields = ("venue__name", "contact__first_name", "contact__last_name", "contact__email")
    autocomplete_fields = ("venue", "contact")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        was_active = form.initial.get("is_active", True)
        super().save_model(request, obj, form, change)
        action = (
            "venue.contact_added"
            if not change
            else (
                "venue.contact_removed"
                if was_active and not obj.is_active
                else "venue.contact_updated"
            )
        )
        record_event(
            actor=request.user,
            organization=obj.venue.organization,
            action=action,
            resource=obj.venue,
            description=f"Updated a contact relationship for {obj.venue.name} in admin.",
            request=request,
        )
