from rest_framework.permissions import BasePermission, IsAuthenticated

from organizations.permissions import (
    get_active_membership,
    user_has_organization_access,
    user_has_organization_permission,
)


class AuthenticatedUser(IsAuthenticated):
    pass


class PlatformSuperuser(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and request.user.is_superuser
        )


class ActiveOrganizationMember(BasePermission):
    def has_object_permission(self, request, view, organization):
        return user_has_organization_access(request.user, organization)


class ArtistAccess(BasePermission):
    def has_object_permission(self, request, view, organization):
        return user_has_organization_permission(request.user, organization, "portal.artist")

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        organization = getattr(view, "organization", None)
        if organization is None:
            return False
        return get_active_membership(request.user, organization) is not None and (
            user_has_organization_permission(request.user, organization, "portal.artist")
        )
