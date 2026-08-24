from django.contrib import admin
from unfold.admin import ModelAdmin

from core.admin import PlatformSuperuserAdminMixin

from .admin_forms import MembershipAdminForm
from .models import Invitation, Membership, Organization


@admin.register(Organization)
class OrganizationAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    readonly_fields = ("id", "created_at", "updated_at")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    list_per_page = 50
    fieldsets = (
        ("Organization", {"fields": ("id", "name", "slug")}),
        ("Status", {"fields": ("is_active",)}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Membership)
class MembershipAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    form = MembershipAdminForm
    list_display = ("user", "organization", "role", "is_active", "created_at")
    list_filter = ("role", "is_active", "organization")
    search_fields = ("user__email", "organization__name")
    autocomplete_fields = ("user", "organization")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("organization", "user__email")
    list_per_page = 50
    fieldsets = (
        ("Membership", {"fields": ("id", "organization", "user", "role")}),
        ("Status", {"fields": ("is_active",)}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Invitation)
class InvitationAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("email", "organization", "role", "expires_at", "accepted_at", "revoked_at")
    list_filter = ("role", "organization", "accepted_at", "revoked_at")
    search_fields = ("email", "organization__name")
    readonly_fields = (
        "id",
        "organization",
        "email",
        "role",
        "invited_by",
        "created_at",
        "updated_at",
        "expires_at",
        "accepted_at",
        "revoked_at",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 50
    fieldsets = (
        ("Invitation", {"fields": ("id", "organization", "email", "role", "invited_by")}),
        (
            "Lifecycle",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "expires_at",
                    "accepted_at",
                    "revoked_at",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
