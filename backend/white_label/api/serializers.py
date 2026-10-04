from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from white_label.models import (
    APIClient,
    GlobalBranding,
    APIKey,
    OrganizationBranding,
    OrganizationDomain,
    validate_theme_contrast,
)
from white_label.services import ALLOWED_SCOPES, effective_branding, effective_global_branding


class BrandingSerializer(serializers.ModelSerializer):
    effective = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = OrganizationBranding
        fields = (
            "id",
            "organization",
            "display_name",
            "logo_url",
            "favicon_url",
            "primary_color",
            "secondary_color",
            "accent_color",
            "background_color",
            "surface_color",
            "text_color",
            "text_muted_color",
            "seo_title",
            "seo_description",
            "og_image_url",
            "support_email",
            "support_url",
            "effective",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization", "effective", "created_at", "updated_at")

    def get_mobile_icon_asset_url(self, branding):
        return "/api/branding/public-assets/mobile_icon/" if branding.pk and branding.assets.filter(asset_type="mobile_icon").exists() else ""

    def get_effective(self, branding):
        return effective_branding(branding.organization)

    def validate(self, attrs):
        instance = self.instance
        colors = {
            field: attrs.get(field, getattr(instance, field))
            for field in (
                "primary_color",
                "accent_color",
                "background_color",
                "surface_color",
                "text_color",
                "text_muted_color",
            )
        }
        try:
            validate_theme_contrast(colors)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict) from error
        return attrs


class DomainSerializer(serializers.ModelSerializer):
    verification_name = serializers.CharField(read_only=True)
    verification_record_type = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationDomain
        fields = (
            "id",
            "organization",
            "hostname",
            "verification_status",
            "verification_record_type",
            "verification_name",
            "verification_token",
            "verified_at",
            "is_active",
            "is_primary",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "verification_status",
            "verification_record_type",
            "verification_name",
            "verification_token",
            "verified_at",
            "created_at",
            "updated_at",
        )

    def get_verification_record_type(self, domain):
        return "TXT"


class APIKeySerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = APIKey
        fields = (
            "id",
            "key_prefix",
            "scopes",
            "status",
            "created_at",
            "last_used_at",
            "expires_at",
            "revoked_at",
        )

    def get_status(self, key):
        if key.revoked_at:
            return "revoked"
        if key.expires_at and key.expires_at <= timezone.now():
            return "expired"
        if not key.client.is_active:
            return "inactive"
        return "active"


class APIClientSerializer(serializers.ModelSerializer):
    keys = APIKeySerializer(many=True, read_only=True)

    class Meta:
        model = APIClient
        fields = (
            "id",
            "organization",
            "name",
            "description",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
            "keys",
        )
        read_only_fields = ("id", "organization", "created_by", "created_at", "updated_at", "keys")


class APIClientCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    description = serializers.CharField(
        max_length=1000, required=False, allow_blank=True, default=""
    )
    scopes = serializers.MultipleChoiceField(choices=ALLOWED_SCOPES)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_expires_at(self, value):
        from django.utils import timezone

        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiry must be in the future.")
        return value


class GlobalBrandingSerializer(serializers.ModelSerializer):
    logo_asset_url = serializers.SerializerMethodField(read_only=True)
    dark_logo_asset_url = serializers.SerializerMethodField(read_only=True)
    favicon_asset_url = serializers.SerializerMethodField(read_only=True)
    mobile_icon_asset_url = serializers.SerializerMethodField(read_only=True)
    effective = serializers.SerializerMethodField(read_only=True)

    def get_mobile_icon_asset_url(self, branding):
        return "/api/branding/public-assets/mobile_icon/" if branding.pk and branding.assets.filter(asset_type="mobile_icon").exists() else ""

    def get_effective(self, branding):
        return effective_global_branding()

    def get_logo_asset_url(self, branding):
        return "/api/branding/public-assets/logo/" if branding.pk and branding.assets.filter(asset_type="logo").exists() else ""

    def get_dark_logo_asset_url(self, branding):
        return "/api/branding/public-assets/dark_logo/" if branding.pk and branding.assets.filter(asset_type="dark_logo").exists() else ""

    def get_favicon_asset_url(self, branding):
        return "/api/branding/public-assets/favicon/" if branding.pk and branding.assets.filter(asset_type="favicon").exists() else ""

    class Meta:
        model = GlobalBranding
        fields = (
            "id", "override_organizations", "display_name", "application_title", "logo_url", "favicon_url", "mobile_icon_url",
            "logo_asset_url", "dark_logo_asset_url", "favicon_asset_url", "mobile_icon_asset_url", "effective",
            "primary_color", "secondary_color", "accent_color", "background_color",
            "surface_color", "text_color", "text_muted_color", "seo_title",
            "seo_description", "og_image_url", "support_email", "support_url",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        instance = self.instance
        colors = {field: attrs.get(field, getattr(instance, field, "")) for field in ("primary_color", "accent_color", "background_color", "surface_color", "text_color", "text_muted_color")}
        if any(colors.values()) and not all(colors.values()):
            raise serializers.ValidationError("Provide all theme colors together or leave them blank.")
        if all(colors.values()):
            try:
                validate_theme_contrast(colors)
            except DjangoValidationError as error:
                raise serializers.ValidationError(error.message_dict) from error
        return attrs
