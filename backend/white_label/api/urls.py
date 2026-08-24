from django.urls import path

from .views import (
    APIClientDetailView,
    APIClientListView,
    APIKeyRevokeView,
    CurrentBrandingView,
    DeveloperMetadataView,
    DeveloperWhoAmIView,
    OrganizationBrandingView,
    OrganizationDomainListView,
    PlatformBrandingDetailView,
    PlatformBrandingListView,
    PlatformDomainDetailView,
    PlatformDomainListView,
)

urlpatterns = [
    path("branding/current/", CurrentBrandingView.as_view(), name="current-branding"),
    path(
        "organizations/<uuid:organization_id>/branding/",
        OrganizationBrandingView.as_view(),
        name="organization-branding",
    ),
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
