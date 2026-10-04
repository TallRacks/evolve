from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from unfold.admin import ModelAdmin

from core.admin import PlatformSuperuserAdminMixin

from .models import APIClient, APIKey, GlobalBranding, GlobalBrandingAsset, OrganizationBranding, OrganizationDomain
from .services import upload_global_branding_asset


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


class GlobalBrandingAdminForm(forms.ModelForm):
    logo_file = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={"accept": ".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"}), help_text="PNG, JPEG, or WebP. Uploading replaces the current stored logo.")
    dark_logo_file = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={"accept": ".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"}), help_text="Logo used on dark mode.")
    favicon_file = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={"accept": ".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"}), help_text="PNG, JPEG, or WebP. Uploading replaces the current stored favicon.")

    class Meta:
        model = GlobalBranding
        fields = "__all__"


@admin.register(GlobalBranding)
class GlobalBrandingAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    form = GlobalBrandingAdminForm
    list_display = ("display_name", "override_organizations", "updated_at")
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (("Global identity", {"fields": ("id", "override_organizations", "display_name", "logo_url", "favicon_url")}), ("Upload assets", {"fields": ("logo_file", "dark_logo_file", "favicon_file")}), ("Theme", {"fields": ("primary_color", "secondary_color", "accent_color", "background_color", "surface_color", "text_color", "text_muted_color")}), ("SEO and support", {"fields": ("seo_title", "seo_description", "og_image_url", "support_email", "support_url")}), ("Metadata", {"fields": ("created_at", "updated_at")}))

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        for asset_type, field_name in ((GlobalBrandingAsset.AssetType.LOGO, "logo_file"), (GlobalBrandingAsset.AssetType.DARK_LOGO, "dark_logo_file"), (GlobalBrandingAsset.AssetType.FAVICON, "favicon_file")):
            uploaded = form.cleaned_data.get(field_name)
            if uploaded:
                try:
                    upload_global_branding_asset(
                        actor=request.user, branding=obj, asset_type=asset_type,
                        file=uploaded, request=request,
                    )
                except (ValidationError, ValueError) as error:
                    raise ValidationError({field_name: str(error)}) from error

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GlobalBrandingAsset)
class GlobalBrandingAssetAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("asset_type", "branding", "original_filename", "file_size", "created_at")
    list_filter = ("asset_type", "content_type")
    search_fields = ("original_filename", "checksum_sha256")
    readonly_fields = ("id", "branding", "asset_type", "storage_provider", "storage_key", "original_filename", "content_type", "file_size", "checksum_sha256", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
