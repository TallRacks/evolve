from django.contrib.auth.models import AnonymousUser

from .models import Membership, Organization

ROLE_PERMISSIONS = {
    Membership.Role.OWNER: {"*"},
    Membership.Role.ADMIN: {
        "organization.view",
        "organization.manage",
        "membership.view",
        "membership.manage",
    },
    Membership.Role.MANAGER: {"organization.view", "membership.view"},
    Membership.Role.MEMBER: {"organization.view"},
    Membership.Role.ARTIST: {"organization.view", "portal.artist"},
}


def permissions_for_role(role: str) -> list[str]:
    permissions = ROLE_PERMISSIONS.get(role, set())
    if "*" in permissions:
        return ["organization.manage", "organization.view", "membership.manage", "membership.view"]
    return sorted(permissions)


def get_active_membership(user, organization: Organization) -> Membership | None:
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return None
    return (
        Membership.objects.active()
        .filter(user=user, organization=organization)
        .select_related("organization", "user")
        .first()
    )


def user_has_organization_access(user, organization: Organization) -> bool:
    if not user or not user.is_authenticated or not user.is_active or not organization.is_active:
        return False
    if user.is_superuser:
        return True
    return get_active_membership(user, organization) is not None


def user_has_organization_permission(user, organization: Organization, permission: str) -> bool:
    if not user_has_organization_access(user, organization):
        return False
    if user.is_superuser:
        return True
    membership = get_active_membership(user, organization)
    if membership is None:
        return False
    permissions = ROLE_PERMISSIONS.get(membership.role, set())
    return "*" in permissions or permission in permissions
