from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from audit.services import record_event
from organizations.permissions import user_has_organization_permission

from .models import Venue, VenueContact


def require_venue_permission(actor, organization, permission):
    if getattr(actor, "is_active", False) and getattr(actor, "is_superuser", False):
        return
    if not user_has_organization_permission(actor, organization, permission):
        raise PermissionDenied("You do not have permission to manage this venue.")


@transaction.atomic
def create_venue(*, actor, organization, data, request=None):
    require_venue_permission(actor, organization, "venue.manage")
    venue = Venue(organization=organization, **data)
    venue.full_clean()
    venue.save()
    record_event(
        actor=actor,
        organization=organization,
        action="venue.created",
        resource=venue,
        description=f"Created venue {venue.name}.",
        request=request,
    )
    return venue


@transaction.atomic
def update_venue(*, actor, venue, data, request=None):
    require_venue_permission(actor, venue.organization, "venue.manage")
    previous = venue.status
    for field, value in data.items():
        setattr(venue, field, value)
    venue.full_clean()
    venue.save()
    action = "venue.updated"
    if previous != venue.status:
        action = "venue.reactivated" if venue.status == Venue.Status.ACTIVE else "venue.deactivated"
    record_event(
        actor=actor,
        organization=venue.organization,
        action=action,
        resource=venue,
        description=f"Updated venue {venue.name}.",
        request=request,
    )
    return venue


@transaction.atomic
def add_venue_contact(*, actor, venue, contact, data, request=None):
    require_venue_permission(actor, venue.organization, "venue.manage")
    link = VenueContact.objects.select_for_update().filter(venue=venue, contact=contact).first()
    if link and link.is_active:
        raise ValidationError("This contact is already linked to the venue.")
    if link:
        link.responsibility = data["responsibility"]
        link.is_primary = data.get("is_primary", False)
        link.is_active = True
    else:
        link = VenueContact(venue=venue, contact=contact, **data)
    link.full_clean()
    link.save()
    record_event(
        actor=actor,
        organization=venue.organization,
        action="venue.contact_added",
        resource=venue,
        description=f"Added a contact relationship to {venue.name}.",
        request=request,
    )
    return link


@transaction.atomic
def update_venue_contact(*, actor, link, data, request=None):
    require_venue_permission(actor, link.venue.organization, "venue.manage")
    was_active = link.is_active
    for field, value in data.items():
        setattr(link, field, value)
    link.full_clean()
    link.save()
    action = (
        "venue.contact_removed" if was_active and not link.is_active else "venue.contact_updated"
    )
    record_event(
        actor=actor,
        organization=link.venue.organization,
        action=action,
        resource=link.venue,
        description=f"Updated a contact relationship for {link.venue.name}.",
        request=request,
    )
    return link
