from django.contrib import admin
from unfold.admin import ModelAdmin

from audit.services import record_event
from core.admin import PlatformSuperuserAdminMixin

from .models import Artist, ArtistPortalLink, ArtistTeamAssignment


@admin.register(Artist)
class ArtistAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "stage_name",
        "organization",
        "status",
        "city",
        "country",
        "created_at",
    )
    list_filter = ("organization", "status", "country")
    search_fields = ("stage_name", "legal_name", "email", "management_email")
    autocomplete_fields = ("organization",)
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        (
            "Identity",
            {"fields": ("id", "organization", "stage_name", "legal_name", "slug")},
        ),
        ("Status", {"fields": ("status",)}),
        ("Contact", {"fields": ("email", "phone")}),
        ("Management", {"fields": ("management_email", "booking_email")}),
        ("Location", {"fields": ("country", "city")}),
        ("Profile", {"fields": ("website", "biography", "profile_image_url")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        action = "artist.updated" if change else "artist.created"
        if change and "status" in form.changed_data:
            action = {
                Artist.Status.ACTIVE: "artist.activated",
                Artist.Status.INACTIVE: "artist.deactivated",
                Artist.Status.ARCHIVED: "artist.archived",
            }[obj.status]
        record_event(
            actor=request.user,
            organization=obj.organization,
            action=action,
            resource=obj,
            description=f"{'Updated' if change else 'Created'} artist {obj.stage_name} in admin.",
            request=request,
        )


@admin.register(ArtistTeamAssignment)
class ArtistTeamAssignmentAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "artist",
        "member_email",
        "responsibility",
        "is_primary",
        "is_active",
        "created_at",
    )
    list_filter = ("artist__organization", "responsibility", "is_primary", "is_active")
    search_fields = ("artist__stage_name", "membership__user__email")
    autocomplete_fields = ("artist", "membership")
    readonly_fields = ("id", "created_at", "updated_at")

    @admin.display(description="Member")
    def member_email(self, obj):
        return obj.membership.user.email

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        was_active = form.initial.get("is_active", True)
        super().save_model(request, obj, form, change)
        action = "artist.team_updated" if change else "artist.team_assigned"
        if change and was_active and not obj.is_active:
            action = "artist.team_removed"
        record_event(
            actor=request.user,
            organization=obj.artist.organization,
            action=action,
            resource=obj.artist,
            description=f"Updated team assignment for {obj.artist.stage_name} in admin.",
            request=request,
        )


@admin.register(ArtistPortalLink)
class ArtistPortalLinkAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("artist", "user", "relationship", "is_active", "created_at")
    list_filter = ("artist__organization", "relationship", "is_active")
    search_fields = ("artist__stage_name", "user__email")
    autocomplete_fields = ("artist", "user")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        was_active = form.initial.get("is_active", True)
        super().save_model(request, obj, form, change)
        action = "artist.portal_user_linked"
        if change and was_active and not obj.is_active:
            action = "artist.portal_user_unlinked"
        record_event(
            actor=request.user,
            organization=obj.artist.organization,
            action=action,
            resource=obj.artist,
            description=f"Updated portal link for {obj.artist.stage_name} in admin.",
            request=request,
        )
