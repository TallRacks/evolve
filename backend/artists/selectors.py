from audit.models import AuditEvent
from organizations.models import Membership
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user

from .models import Artist


def artists_for_user(user):
    if user and user.is_authenticated and user.is_active and user.is_superuser:
        return Artist.objects.select_related("organization").all()
    return Artist.objects.filter(
        organization_id__in=organizations_for_user(user).values("pk")
    ).select_related("organization")


def artist_activity(artist):
    return AuditEvent.objects.filter(
        organization=artist.organization,
        resource_type="Artist",
        resource_id=str(artist.pk),
        action__startswith="artist.",
    ).select_related("actor")[:100]


def portal_artists_for_user(user):
    if not user or not user.is_authenticated or not user.is_active or user.is_superuser:
        return Artist.objects.none()
    organization_ids = (
        Membership.objects.active()
        .filter(user=user, role=Membership.Role.ARTIST)
        .values("organization_id")
    )
    return (
        Artist.objects.filter(
            organization_id__in=organization_ids,
            organization__is_active=True,
            status__in=(Artist.Status.ACTIVE, Artist.Status.INACTIVE),
            portal_links__user=user,
            portal_links__is_active=True,
        )
        .select_related("organization")
        .distinct()
    )


def can_view_artist(user, artist):
    return user_has_organization_permission(user, artist.organization, "artist.view")
