from django.urls import path

from . import views
from .views import (
    InvitationAcceptView,
    InvitationSignupView,
    InvitationDetailView,
    OrganizationDetailView,
    OrganizationInvitationListView,
    OrganizationListView,
    OrganizationMemberListView,
    PlatformOrganizationDetailView,
    PlatformOrganizationMemberListView,
    PlatformOrganizationListView,
    PlatformOverviewView,
    PlatformUserDetailView,
    PlatformUserListView,
    ProfileView, ProfileImageView,
    RoleCatalogView,
)

app_name = "organizations_api"
urlpatterns = [
    path("roles/", RoleCatalogView.as_view(), name="role-catalog"),
    path("organizations/", OrganizationListView.as_view(), name="organization-list"),
    path(
        "organizations/<uuid:organization_id>/",
        OrganizationDetailView.as_view(),
        name="organization-detail",
    ),
    path(
        "organizations/<uuid:organization_id>/members/",
        OrganizationMemberListView.as_view(),
        name="member-list",
    ),
    path(
        "organizations/<uuid:organization_id>/members/<uuid:membership_id>/",
        OrganizationMemberListView.as_view(),
        name="member-detail",
    ),
    path("organizations/<uuid:organization_id>/members/<uuid:membership_id>/scope/", views.MembershipScopePreviewView.as_view(), name="member-scope"),
    path("organizations/<uuid:organization_id>/features/", views.FeatureSettingListView.as_view(), name="feature-list"),
    path("organizations/<uuid:organization_id>/features/<uuid:feature_id>/", views.FeatureSettingListView.as_view(), name="feature-detail"),
    path(
        "organizations/<uuid:organization_id>/invitations/",
        OrganizationInvitationListView.as_view(),
        name="invitation-list",
    ),
    path(
        "invitations/<uuid:invitation_id>/revoke/",
        InvitationDetailView.as_view(),
        name="invitation-revoke",
    ),
    path("invitations/accept/", InvitationAcceptView.as_view(), name="invitation-accept"),
    path("invitations/signup/", InvitationSignupView.as_view(), name="invitation-signup"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("platform/overview/", PlatformOverviewView.as_view(), name="platform-overview"),
    path(
        "platform/organizations/",
        PlatformOrganizationListView.as_view(),
        name="platform-organizations",
    ),
    path(
        "platform/organizations/<uuid:organization_id>/",
        PlatformOrganizationDetailView.as_view(),
        name="platform-organization-detail",
    ),
    path(
        "platform/organizations/<uuid:organization_id>/members/",
        PlatformOrganizationMemberListView.as_view(),
        name="platform-organization-member-list",
    ),
    path("platform/users/", PlatformUserListView.as_view(), name="platform-users"),
    path(
        "platform/users/<uuid:user_id>/",
        PlatformUserDetailView.as_view(),
        name="platform-user-detail",
    ),
]
