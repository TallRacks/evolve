from django.contrib import admin
from unfold.admin import ModelAdmin

from core.admin import PlatformSuperuserAdminMixin

from .models import APIClient, APIKey, OrganizationBranding, OrganizationDomain


@admin.register(OrganizationBranding)
class OrganizationBrandingAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("organization", "display_name", "primary_color", "updated_at")
    search_fields = ("organization__name", "display_name", "support_email")
    autocomplete_fields = ("organization",)
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        ("Organization", {"fields": ("id", "organization", "display_name")}),
        ("Assets", {"fields": ("logo_url", "favicon_url")}),
        (
            "Theme",
            {
                "fields": (
                    "primary_color",
                    "secondary_color",
                    "accent_color",
                    "background_color",
                    "surface_color",
                    "text_color",
                    "text_muted_color",
                )
            },
        ),
        ("Support", {"fields": ("support_email", "support_url")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrganizationDomain)
class OrganizationDomainAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("hostname", "organization", "verification_status", "is_active", "is_primary")
    list_filter = ("verification_status", "is_active", "is_primary")
    search_fields = ("hostname", "organization__name")
    autocomplete_fields = ("organization",)
    readonly_fields = ("id", "verification_token", "verified_at", "created_at", "updated_at")
    fieldsets = (
        ("Domain", {"fields": ("id", "organization", "hostname")}),
        ("Verification", {"fields": ("verification_status", "verification_token", "verified_at")}),
        ("Serving", {"fields": ("is_active", "is_primary")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False


class APIKeyInline(admin.TabularInline):
    model = APIKey
    extra = 0
    can_delete = False
    fields = ("key_prefix", "scopes", "created_at", "last_used_at", "expires_at", "revoked_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(APIClient)
class APIClientAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("name", "organization", "is_active", "created_by", "created_at")
    list_filter = ("is_active", "organization")
    search_fields = ("name", "organization__name")
    autocomplete_fields = ("organization", "created_by")
    readonly_fields = ("id", "created_by", "created_at", "updated_at")
    inlines = (APIKeyInline,)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(APIKey)
class APIKeyAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "key_prefix",
        "client",
        "created_at",
        "last_used_at",
        "expires_at",
        "revoked_at",
    )
    list_filter = ("revoked_at", "client__organization")
    search_fields = ("key_prefix", "client__name", "client__organization__name")
    readonly_fields = (
        "id",
        "client",
        "key_prefix",
        "scopes",
        "created_at",
        "last_used_at",
        "expires_at",
        "revoked_at",
    )
    exclude = ("secret_digest",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
