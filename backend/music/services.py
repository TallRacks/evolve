from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from audit.services import record_event
from notifications.services import artist_team_users, create_notification
from organizations.permissions import user_has_organization_permission

from .models import MusicCredit, Release, ReleaseLink, ReleaseTrack, Track

RELEASE_TRANSITIONS = {
    Release.Status.DRAFT: {Release.Status.SCHEDULED, Release.Status.CANCELLED},
    Release.Status.SCHEDULED: {
        Release.Status.DRAFT,
        Release.Status.RELEASED,
        Release.Status.CANCELLED,
    },
    Release.Status.RELEASED: {Release.Status.ARCHIVED},
    Release.Status.CANCELLED: set(),
    Release.Status.ARCHIVED: set(),
}


def require_music_permission(actor, organization, permission):
    if getattr(actor, "is_active", False) and getattr(actor, "is_superuser", False):
        return
    if not user_has_organization_permission(actor, organization, permission):
        raise PermissionDenied("You do not have permission for this music catalog.")


def allowed_release_transitions(release):
    return sorted(RELEASE_TRANSITIONS[release.status])


@transaction.atomic
def create_release(*, actor, organization, data, request=None):
    require_music_permission(actor, organization, "music.release.manage")
    release = Release(organization=organization, created_by=actor, **data)
    release.save()
    record_event(
        actor=actor,
        organization=organization,
        action="release.created",
        resource=release,
        description=f"Created release {release.title}.",
        request=request,
    )
    return release


@transaction.atomic
def update_release(*, actor, release, data, request=None):
    require_music_permission(actor, release.organization, "music.release.manage")
    if "status" in data:
        raise ValidationError("Use the Release lifecycle service.")
    for field, value in data.items():
        setattr(release, field, value)
    release.save()
    record_event(
        actor=actor,
        organization=release.organization,
        action="release.updated",
        resource=release,
        description=f"Updated release {release.title}.",
        request=request,
    )
    return release


@transaction.atomic
def transition_release(*, actor, release, to_status, reason="", request=None):
    require_music_permission(actor, release.organization, "music.release.manage")
    locked = Release.objects.select_for_update().get(pk=release.pk)
    if to_status not in RELEASE_TRANSITIONS[locked.status]:
        raise ValidationError(f"Cannot transition Release from {locked.status} to {to_status}.")
    if to_status == Release.Status.SCHEDULED and not locked.planned_release_date:
        raise ValidationError("Scheduled releases require a planned release date.")
    from_status = locked.status
    Release.objects.filter(pk=locked.pk).update(status=to_status)
    locked.refresh_from_db()
    action = (
        "release.archived" if to_status == Release.Status.ARCHIVED else "release.status_changed"
    )
    record_event(
        actor=actor,
        organization=locked.organization,
        action=action,
        resource=locked,
        description=f"Changed release {locked.title} from {from_status} to {to_status}.",
        request=request,
    )
    if to_status in (Release.Status.SCHEDULED, Release.Status.RELEASED):
        create_notification(
            organization=locked.organization,
            notification_type=f"release.{to_status}",
            category="music",
            title=f"Release {to_status}",
            message=f"{locked.title} is now {to_status}.",
            users=artist_team_users(locked.primary_artist),
            actor=actor,
            source=locked,
            action_url=f"/workspace/music/releases/{locked.pk}",
        )
    return locked


@transaction.atomic
def create_track(*, actor, organization, data, request=None):
    require_music_permission(actor, organization, "music.track.manage")
    track = Track(organization=organization, created_by=actor, **data)
    track.save()
    record_event(
        actor=actor,
        organization=organization,
        action="track.created",
        resource=track,
        description=f"Created track {track.title}.",
        request=request,
    )
    return track


@transaction.atomic
def update_track(*, actor, track, data, request=None):
    require_music_permission(actor, track.organization, "music.track.manage")
    previous_status = track.status
    for field, value in data.items():
        setattr(track, field, value)
    track.save()
    action = (
        "track.archived"
        if previous_status != track.status and track.status == Track.Status.ARCHIVED
        else "track.updated"
    )
    record_event(
        actor=actor,
        organization=track.organization,
        action=action,
        resource=track,
        description=f"Updated track {track.title}.",
        request=request,
    )
    return track


@transaction.atomic
def add_release_track(*, actor, release, track, data, request=None):
    require_music_permission(actor, release.organization, "music.release.manage")
    placement = ReleaseTrack(release=release, track=track, **data)
    placement.save()
    record_event(
        actor=actor,
        organization=release.organization,
        action="release.track_added",
        resource=release,
        description=f"Added {track.title} to {release.title}.",
        request=request,
    )
    return placement


@transaction.atomic
def update_release_track(*, actor, placement, data, request=None):
    require_music_permission(actor, placement.release.organization, "music.release.manage")
    for field, value in data.items():
        setattr(placement, field, value)
    placement.save()
    record_event(
        actor=actor,
        organization=placement.release.organization,
        action="release.track_reordered",
        resource=placement.release,
        description=f"Updated track order on {placement.release.title}.",
        request=request,
    )
    return placement


@transaction.atomic
def remove_release_track(*, actor, placement, request=None):
    require_music_permission(actor, placement.release.organization, "music.release.manage")
    release = placement.release
    title = placement.track.title
    placement.delete()
    record_event(
        actor=actor,
        organization=release.organization,
        action="release.track_removed",
        resource=release,
        description=f"Removed {title} from {release.title}.",
        request=request,
    )


def _credit_permission(credit_or_organization):
    return getattr(credit_or_organization, "organization", credit_or_organization)


@transaction.atomic
def create_credit(*, actor, organization, data, resource, request=None):
    require_music_permission(actor, organization, "music.credits.manage")
    credit = MusicCredit(organization=organization, **data)
    credit.save()
    record_event(
        actor=actor,
        organization=organization,
        action="music.credit_added",
        resource=resource,
        description=f"Added {credit.credit_role} credit.",
        request=request,
    )
    return credit


@transaction.atomic
def update_credit(*, actor, credit, data, resource, request=None):
    require_music_permission(actor, credit.organization, "music.credits.manage")
    for field, value in data.items():
        setattr(credit, field, value)
    credit.save()
    record_event(
        actor=actor,
        organization=credit.organization,
        action="music.credit_updated",
        resource=resource,
        description="Updated music credit.",
        request=request,
    )
    return credit


@transaction.atomic
def remove_credit(*, actor, credit, resource, request=None):
    require_music_permission(actor, credit.organization, "music.credits.manage")
    organization = credit.organization
    credit.delete()
    record_event(
        actor=actor,
        organization=organization,
        action="music.credit_removed",
        resource=resource,
        description="Removed music credit.",
        request=request,
    )


@transaction.atomic
def create_link(*, actor, release, data, request=None):
    require_music_permission(actor, release.organization, "music.release.manage")
    link = ReleaseLink(release=release, **data)
    link.full_clean()
    link.save()
    record_event(
        actor=actor,
        organization=release.organization,
        action="music.link_added",
        resource=release,
        description=f"Added {link.platform} release link.",
        request=request,
    )
    return link


@transaction.atomic
def update_link(*, actor, link, data, request=None):
    require_music_permission(actor, link.release.organization, "music.release.manage")
    for field, value in data.items():
        setattr(link, field, value)
    link.full_clean()
    link.save()
    record_event(
        actor=actor,
        organization=link.release.organization,
        action="music.link_updated",
        resource=link.release,
        description=f"Updated {link.platform} release link.",
        request=request,
    )
    return link


@transaction.atomic
def remove_link(*, actor, link, request=None):
    require_music_permission(actor, link.release.organization, "music.release.manage")
    release = link.release
    link.delete()
    record_event(
        actor=actor,
        organization=release.organization,
        action="music.link_removed",
        resource=release,
        description="Removed release link.",
        request=request,
    )
