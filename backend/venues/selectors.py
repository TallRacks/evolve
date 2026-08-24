from audit.models import AuditEvent
from organizations.selectors import organizations_for_user

from .models import Venue


def venues_for_user(user):
    if user and user.is_authenticated and user.is_active and user.is_superuser:
        return Venue.objects.select_related("organization").all()
    return Venue.objects.filter(
        organization_id__in=organizations_for_user(user).values("pk")
    ).select_related("organization")


def venue_activity(venue):
    return AuditEvent.objects.filter(
        organization=venue.organization,
        resource_type="Venue",
        resource_id=str(venue.pk),
        action__startswith="venue.",
    ).select_related("actor")[:100]
