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
        "document.view",
    },
    Membership.Role.ARTIST: {"organization.view", "portal.artist"},
}


def permissions_for_role(role: str) -> list[str]:
    permissions = ROLE_PERMISSIONS.get(role, set())
    if "*" in permissions:
        return sorted(
            {
                permission
                for values in ROLE_PERMISSIONS.values()
                for permission in values
                if permission != "*"
            }
        )
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
