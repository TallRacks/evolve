from django.urls import path

from .views import (
    APIClientDetailView,
    APIClientListView,
    APIKeyRevokeView,
    CurrentBrandingView,
    PublicBrandingAssetView,
    DeveloperMetadataView,
    DeveloperWhoAmIView,
    OrganizationBrandingView,
    OrganizationBrandingAssetView,
    OrganizationDomainListView,
    GlobalBrandingView,
    GlobalBrandingAssetView,
    GlobalBrandingAssetPreviewView,
    PlatformBrandingDetailView,
    PlatformBrandingListView,
    PlatformDomainDetailView,
    PlatformDomainListView,
)

urlpatterns = [
    path("branding/current/", CurrentBrandingView.as_view(), name="current-branding"),
    path("branding/public-assets/<str:asset_type>/", PublicBrandingAssetView.as_view(), name="public-branding-asset"),
    path("organizations/<uuid:organization_id>/branding/", OrganizationBrandingView.as_view(), name="organization-branding"),
    path("organizations/<uuid:organization_id>/branding/assets/", OrganizationBrandingAssetView.as_view(), name="organization-branding-assets"),
    path(
        "organizations/<uuid:organization_id>/domains/",
        OrganizationDomainListView.as_view(),
        name="organization-domains",
    ),
    path(
        "organizations/<uuid:organization_id>/api-clients/",
        APIClientListView.as_view(),
        name="api-clients",
    ),
    path(
        "organizations/<uuid:organization_id>/api-keys/<uuid:key_id>/revoke/",
        APIKeyRevokeView.as_view(),
        name="api-key-revoke",
    ),
    path("platform/global-branding/", GlobalBrandingView.as_view(), name="platform-global-branding"),
    path("platform/global-branding/assets/", GlobalBrandingAssetView.as_view(), name="platform-global-branding-assets"),
    path("platform/global-branding/assets/<str:asset_type>/preview/", GlobalBrandingAssetPreviewView.as_view(), name="platform-global-branding-asset-preview"),
    path("platform/branding/", PlatformBrandingListView.as_view(), name="platform-branding"),
    path(
        "platform/branding/<uuid:organization_id>/",
        PlatformBrandingDetailView.as_view(),
        name="platform-branding-detail",
    ),
    path(
        "organizations/<uuid:organization_id>/api-clients/<uuid:client_id>/deactivate/",
        APIClientDetailView.as_view(),
        name="api-client-detail",
    ),
    path("platform/domains/", PlatformDomainListView.as_view(), name="platform-domains"),
    path(
        "platform/domains/<uuid:domain_id>/",
        PlatformDomainDetailView.as_view(),
        name="platform-domain-detail",
    ),
    path("developer/metadata/", DeveloperMetadataView.as_view(), name="developer-metadata"),
    path("developer/whoami/", DeveloperWhoAmIView.as_view(), name="developer-whoami"),
]
