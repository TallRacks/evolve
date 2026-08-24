from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from audit.services import record_event
from organizations.permissions import user_has_organization_permission

from .models import Artist, ArtistPortalLink, ArtistTeamAssignment


def require_artist_permission(actor, organization, permission):
    if getattr(actor, "is_active", False) and getattr(actor, "is_superuser", False):
        return
    if not user_has_organization_permission(actor, organization, permission):
        raise PermissionDenied("You do not have permission to manage this artist.")


@transaction.atomic
def create_artist(*, actor, organization, data, request=None):
    require_artist_permission(actor, organization, "artist.manage")
    artist = Artist(organization=organization, **data)
    artist.full_clean()
    artist.save()
    record_event(
        actor=actor,
        organization=organization,
        action="artist.created",
        resource=artist,
        description=f"Created artist {artist.stage_name}.",
        request=request,
    )
    return artist


@transaction.atomic
def update_artist(*, actor, artist, data, request=None):
    require_artist_permission(actor, artist.organization, "artist.manage")
    previous_status = artist.status
    for field, value in data.items():
        setattr(artist, field, value)
    artist.full_clean()
    artist.save()
    action = "artist.updated"
    if artist.status != previous_status:
        action = {
            Artist.Status.ACTIVE: "artist.activated",
            Artist.Status.INACTIVE: "artist.deactivated",
            Artist.Status.ARCHIVED: "artist.archived",
        }[artist.status]
    record_event(
        actor=actor,
        organization=artist.organization,
        action=action,
        resource=artist,
        description=f"Updated artist {artist.stage_name}.",
        request=request,
    )
    return artist


@transaction.atomic
def assign_team_member(*, actor, artist, membership, data, request=None):
    require_artist_permission(actor, artist.organization, "artist.team.manage")
    assignment = (
        ArtistTeamAssignment.objects.select_for_update()
        .filter(artist=artist, membership=membership)
        .first()
    )
    if assignment and assignment.is_active:
        raise ValidationError("This membership is already assigned to the artist.")
    if assignment:
        assignment.responsibility = data["responsibility"]
        assignment.is_primary = data.get("is_primary", False)
        assignment.is_active = True
    else:
        assignment = ArtistTeamAssignment(artist=artist, membership=membership, **data)
    assignment.full_clean()
    assignment.save()
    record_event(
        actor=actor,
        organization=artist.organization,
        action="artist.team_assigned",
        resource=artist,
        description=f"Assigned {membership.user.email} to {artist.stage_name}.",
        request=request,
    )
    return assignment


@transaction.atomic
def update_team_assignment(*, actor, assignment, data, request=None):
    require_artist_permission(
        actor, assignment.artist.organization, "artist.team.manage"
    )
    was_active = assignment.is_active
    for field, value in data.items():
        setattr(assignment, field, value)
    assignment.full_clean()
    assignment.save()
    action = (
        "artist.team_removed"
        if was_active and not assignment.is_active
        else "artist.team_updated"
    )
    record_event(
        actor=actor,
        organization=assignment.artist.organization,
        action=action,
        resource=assignment.artist,
        description=f"Updated team assignment for {assignment.artist.stage_name}.",
        request=request,
    )
    return assignment


@transaction.atomic
def link_portal_user(*, actor, artist, user, relationship, request=None):
    require_artist_permission(actor, artist.organization, "artist.team.manage")
    link = (
        ArtistPortalLink.objects.select_for_update()
        .filter(artist=artist, user=user)
        .first()
    )
    if link and link.is_active:
        raise ValidationError("This user is already linked to the artist.")
    if link:
        link.relationship = relationship
        link.is_active = True
    else:
        link = ArtistPortalLink(artist=artist, user=user, relationship=relationship)
    link.full_clean()
    link.save()
    record_event(
        actor=actor,
        organization=artist.organization,
        action="artist.portal_user_linked",
        resource=artist,
        description=f"Linked portal user to {artist.stage_name}.",
        request=request,
    )
    return link


@transaction.atomic
def unlink_portal_user(*, actor, link, request=None):
    require_artist_permission(actor, link.artist.organization, "artist.team.manage")
    if link.is_active:
        link.is_active = False
        link.save(update_fields=("is_active", "updated_at"))
        record_event(
            actor=actor,
            organization=link.artist.organization,
            action="artist.portal_user_unlinked",
            resource=link.artist,
            description=f"Unlinked portal user from {link.artist.stage_name}.",
            request=request,
        )
    return link
