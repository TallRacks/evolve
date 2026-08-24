from audit.models import AuditEvent
from organizations.selectors import organizations_for_user

from .models import Booking


def bookings_for_user(user):
    if user and user.is_authenticated and user.is_active and user.is_superuser:
        return Booking.objects.select_related("organization", "artist", "promoter", "venue").all()
    return Booking.objects.filter(
        organization_id__in=organizations_for_user(user).values("pk")
    ).select_related("organization", "artist", "promoter", "venue")


def booking_activity(booking):
    return AuditEvent.objects.filter(
        organization=booking.organization,
        resource_type="Booking",
        resource_id=str(booking.pk),
        action__startswith="booking.",
    ).select_related("actor")[:100]
