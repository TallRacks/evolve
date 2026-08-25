from audit.models import AuditEvent
from organizations.selectors import organizations_for_user

from .models import TravelItinerary


def itinerary_queryset():
    return TravelItinerary.objects.select_related(
        "organization", "artist", "booking", "created_by"
    ).prefetch_related(
        "travellers__artist",
        "travellers__membership__user",
        "segments__traveller_assignments__traveller",
        "stays__room_assignments__traveller",
    )


def itineraries_for_user(user):
    if not user or not user.is_authenticated or not user.is_active:
        return itinerary_queryset().none()
    if user.is_superuser:
        return itinerary_queryset()
    return itinerary_queryset().filter(
        organization_id__in=organizations_for_user(user).values("pk")
    )


def artist_itineraries_for_user(user):
    from artists.selectors import portal_artists_for_user

    return (
        itinerary_queryset()
        .filter(artist_id__in=portal_artists_for_user(user).values("pk"))
        .exclude(status=TravelItinerary.Status.ARCHIVED)
    )


def itinerary_activity(itinerary):
    return AuditEvent.objects.filter(
        organization=itinerary.organization,
        action__startswith="travel.",
        resource_id=str(itinerary.pk),
    ).select_related("actor")[:100]
