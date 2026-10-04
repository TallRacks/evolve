from django.contrib.auth.models import AnonymousUser

from .models import Membership, Organization

ROLE_PERMISSIONS = {
    Membership.Role.OWNER: {"*"},
    Membership.Role.ADMIN: {
        "organization.view",
        "organization.manage",
        "membership.view",
        "membership.manage",
        "branding.manage",
        "domain.manage",
        "api.manage",
        "artist.view",
        "artist.manage",
        "artist.team.manage",
        "promoter.view",
        "promoter.manage",
        "venue.view",
        "venue.manage",
        "contact.view",
        "contact.manage",
        "booking.view",
        "booking.manage",
        "booking.status.manage",
        "booking.team.manage",
        "booking.commercial.view",
        "booking.commercial.manage",
        "callsheet.view",
        "callsheet.manage",
        "callsheet.publish",
        "music.view",
        "music.manage",
        "music.release.manage",
        "music.track.manage",
        "music.credits.manage",
        "campaign.view",
        "campaign.manage",
        "campaign.status.manage",
        "rollout.view",
        "rollout.manage",
        "rollout.task.manage",
        "task.view",
        "mailbox.view",
        "activity.view",
        "reporting.view",
        "task.manage",
        "task.assign",
        "task.status.manage",
        "mailbox.manage",
        "travel.view",
        "travel.manage",
        "travel.status.manage",
        "travel.private_contact.view",
        "production.view",
        "production.manage",
        "production.status.manage",
        "production.requirements.manage",
        "production.schedule.manage",
        "production.checklist.manage",
        "production.contacts.manage",
        "calendar.view",
        "calendar.manage",
        "document.view",
        "document.manage",
        "document.restricted.view",
        "document_template.view",
        "document_template.manage",
        "finance.view",
        "finance.manage",
        "finance.invoice.issue",
        "finance.payment.record",
        "finance.payment.allocate",
        "rights.view",
        "rights.manage",
        "royalties.view",
        "royalties.manage",
        "royalties.statement.finalize",
        "contract.view",
        "contract.manage",
        "contract.approve",
        "contract.status.manage",
        "contract.sensitive.view",
        "contract.signature.manage",
    },
    Membership.Role.MANAGER: {
        "organization.view",
        "membership.view",
        "artist.view",
        "artist.manage",
        "promoter.view",
        "promoter.manage",
        "venue.view",
        "venue.manage",
        "contact.view",
        "contact.manage",
        "booking.view",
        "booking.manage",
        "booking.status.manage",
        "booking.team.manage",
        "callsheet.view",
        "callsheet.manage",
        "callsheet.publish",
        "music.view",
        "music.manage",
        "music.release.manage",
        "music.track.manage",
        "music.credits.manage",
        "campaign.view",
        "campaign.manage",
        "campaign.status.manage",
        "rollout.view",
        "rollout.manage",
        "rollout.task.manage",
        "task.view",
        "mailbox.view",
        "activity.view",
        "reporting.view",
        "task.manage",
        "task.assign",
        "task.status.manage",
        "mailbox.manage",
        "travel.view",
        "travel.manage",
        "travel.status.manage",
        "travel.private_contact.view",
        "production.view",
        "production.manage",
        "production.status.manage",
        "production.requirements.manage",
        "production.schedule.manage",
        "production.checklist.manage",
        "production.contacts.manage",
        "calendar.view",
        "calendar.manage",
        "document.view",
        "document.manage",
        "document.restricted.view",
        "document_template.view",
        "document_template.manage",
        "contract.view",
        "contract.manage",
        "contract.status.manage",
        "contract.signature.manage",
    },
    Membership.Role.MEMBER: {
        "organization.view",
        "artist.view",
        "promoter.view",
        "venue.view",
        "contact.view",
        "booking.view",
        "callsheet.view",
        "music.view",
        "campaign.view",
        "rollout.view",
        "travel.view",
        "production.view",
        "calendar.view",
        "document_template.view",
        "document.view",
        "task.view",
        "activity.view",
        "reporting.view",
    },
    Membership.Role.ARTIST: {"organization.view", "portal.artist"},
    Membership.Role.ARTIST_MANAGER: {
        "organization.view", "artist.view", "artist.manage", "artist.team.manage",
        "booking.view", "booking.manage", "booking.status.manage", "booking.team.manage",
        "calendar.view", "calendar.manage", "campaign.view", "music.view",
        "document.view", "task.view", "task.manage", "task.assign",
        "travel.view", "production.view", "activity.view",
    },
    Membership.Role.ARTIST_ASSISTANT: {
        "organization.view", "artist.view", "booking.view", "calendar.view",
        "campaign.view", "music.view", "document.view", "task.view", "task.manage",
        "travel.view", "production.view", "activity.view",
    },
    Membership.Role.ARTIST_VIEWER: {
        "organization.view", "artist.view", "booking.view", "calendar.view",
        "campaign.view", "music.view", "document.view", "activity.view",
    },
}


def all_permissions() -> set[str]:
    return {permission for values in ROLE_PERMISSIONS.values() for permission in values if permission != "*"}


def permissions_for_role(role: str, overrides: dict | None = None) -> list[str]:
    permissions = all_permissions() if "*" in ROLE_PERMISSIONS.get(role, set()) else set(ROLE_PERMISSIONS.get(role, set()))
    overrides = overrides or {}
    permissions.update(set(overrides.get("grant", [])) & all_permissions())
    permissions.difference_update(set(overrides.get("deny", [])))
    return sorted(permissions)


def permissions_for_membership(membership: Membership) -> list[str]:
    if membership.role_profile_id and membership.role_profile and membership.role_profile.is_active:
        permissions = set(membership.role_profile.permissions) & all_permissions()
        overrides = membership.permission_overrides or {}
        permissions.update(set(overrides.get("grant", [])) & all_permissions())
        permissions.difference_update(set(overrides.get("deny", [])))
        return sorted(permissions)
    return permissions_for_role(membership.role, membership.permission_overrides)


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
    return permission in permissions_for_membership(membership)


ROLE_DESCRIPTIONS = {
    Membership.Role.OWNER: "Full organization ownership and administration.",
    Membership.Role.ADMIN: "Organization administration and broad operational access.",
    Membership.Role.MANAGER: "Day-to-day operations, team, and workflow management.",
    Membership.Role.MEMBER: "Standard read access to shared operational work.",
    Membership.Role.ARTIST: "Artist portal access for explicitly linked artists.",
    Membership.Role.ARTIST_MANAGER: "Manage an artist's profile, team, bookings, campaigns, and tasks.",
    Membership.Role.ARTIST_ASSISTANT: "Coordinate an artist's schedule, tasks, documents, and operations.",
    Membership.Role.ARTIST_VIEWER: "Read-only artist-centered access to approved workspace records.",
}


def role_catalog() -> list[dict[str, object]]:
    return [
        {
            "value": role.value,
            "label": role.label,
            "description": ROLE_DESCRIPTIONS[role],
            "permissions": permissions_for_role(role),
        }
        for role in Membership.Role
    ]
