from artists.selectors import portal_artists_for_user
from audit.models import AuditEvent
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user

from .models import Release, Track


def releases_for_user(user):
    if user and user.is_authenticated and user.is_active and user.is_superuser:
        return Release.objects.all()
    return Release.objects.filter(organization_id__in=organizations_for_user(user).values("pk"))


def tracks_for_user(user):
    if user and user.is_authenticated and user.is_active and user.is_superuser:
        return Track.objects.all()
    return Track.objects.filter(organization_id__in=organizations_for_user(user).values("pk"))


def portal_releases_for_user(user):
    return Release.objects.filter(
        primary_artist_id__in=portal_artists_for_user(user).values("pk"),
        status__in=(Release.Status.SCHEDULED, Release.Status.RELEASED),
    )


def portal_tracks_for_user(user):
    return Track.objects.filter(
        primary_artist_id__in=portal_artists_for_user(user).values("pk"),
        status=Track.Status.ACTIVE,
    )


def music_activity(resource):
    return AuditEvent.objects.filter(
        organization=resource.organization,
        resource_type=resource.__class__.__name__,
        resource_id=str(resource.pk),
        action__in=(
            "release.created",
            "release.updated",
            "release.status_changed",
            "release.archived",
            "release.track_added",
            "release.track_removed",
            "release.track_reordered",
            "track.created",
            "track.updated",
            "track.archived",
            "music.credit_added",
            "music.credit_updated",
            "music.credit_removed",
            "music.link_added",
            "music.link_updated",
            "music.link_removed",
        ),
    ).select_related("actor")[:100]


def can_view_music(user, organization):
    return user_has_organization_permission(user, organization, "music.view")
