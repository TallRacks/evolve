from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_event
from notifications.models import Notification
from notifications.services import create_notification
from organizations.permissions import user_has_organization_permission

from .models import AccommodationStay, TravelItinerary, TravelSegment

ITINERARY_TRANSITIONS = {
    TravelItinerary.Status.DRAFT: {
        TravelItinerary.Status.CONFIRMED,
        TravelItinerary.Status.CANCELLED,
    },
    TravelItinerary.Status.CONFIRMED: {
        TravelItinerary.Status.IN_PROGRESS,
        TravelItinerary.Status.CANCELLED,
    },
    TravelItinerary.Status.IN_PROGRESS: {
        TravelItinerary.Status.COMPLETED,
        TravelItinerary.Status.CANCELLED,
    },
    TravelItinerary.Status.COMPLETED: {TravelItinerary.Status.ARCHIVED},
    TravelItinerary.Status.CANCELLED: {TravelItinerary.Status.ARCHIVED},
    TravelItinerary.Status.ARCHIVED: set(),
}
SEGMENT_TRANSITIONS = {
    TravelSegment.Status.PLANNED: {TravelSegment.Status.CONFIRMED, TravelSegment.Status.CANCELLED},
    TravelSegment.Status.CONFIRMED: {
        TravelSegment.Status.COMPLETED,
        TravelSegment.Status.CANCELLED,
    },
    TravelSegment.Status.COMPLETED: set(),
    TravelSegment.Status.CANCELLED: set(),
}
STAY_TRANSITIONS = {
    AccommodationStay.Status.PLANNED: {
        AccommodationStay.Status.CONFIRMED,
        AccommodationStay.Status.CANCELLED,
    },
    AccommodationStay.Status.CONFIRMED: {
        AccommodationStay.Status.CHECKED_IN,
        AccommodationStay.Status.CANCELLED,
    },
    AccommodationStay.Status.CHECKED_IN: {
        AccommodationStay.Status.COMPLETED,
        AccommodationStay.Status.CANCELLED,
    },
    AccommodationStay.Status.COMPLETED: set(),
    AccommodationStay.Status.CANCELLED: set(),
}


def require(user, organization, permission):
    if not user_has_organization_permission(user, organization, permission):
        raise PermissionDenied("You do not have permission to manage Travel for this organization.")


def audit(actor, organization, action, resource, description, request=None):
    record_event(
        actor=actor,
        organization=organization,
        action=action,
        resource=resource,
        description=description,
        request=request,
    )


def save_entity(entity, *, actor, permission="travel.manage", action, description, request=None):
    organization = (
        entity.organization if hasattr(entity, "organization") else entity.itinerary.organization
    )
    require(actor, organization, permission)
    entity.save()
    audit(actor, organization, action, entity, description, request)
    return entity


def create_itinerary(*, actor, organization, data, request=None):
    require(actor, organization, "travel.manage")
    data.pop("status", None)
    item = TravelItinerary(organization=organization, created_by=actor, **data)
    return save_entity(
        item,
        actor=actor,
        action="travel.itinerary_created",
        description="Travel itinerary created.",
        request=request,
    )


def update_itinerary(item, *, actor, data, request=None):
    data.pop("status", None)
    data.pop("organization", None)
    data.pop("created_by", None)
    for key, value in data.items():
        setattr(item, key, value)
    return save_entity(
        item,
        actor=actor,
        action="travel.itinerary_updated",
        description="Travel itinerary updated.",
        request=request,
    )


def traveller_users(item):
    return [
        row.membership.user
        for row in item.travellers.filter(is_active=True, membership__isnull=False).select_related(
            "membership__user"
        )
    ]


def notify(item, *, actor, notification_type, title, message):
    create_notification(
        organization=item.organization,
        notification_type=notification_type,
        category=Notification.Category.BOOKINGS,
        title=title,
        message=message,
        users=traveller_users(item),
        actor=actor,
        source=item,
        action_url=f"/workspace/travel/{item.id}",
    )


@transaction.atomic
def transition_itinerary(item, *, actor, to_status, request=None):
    require(actor, item.organization, "travel.status.manage")
    locked = TravelItinerary.objects.select_for_update().get(pk=item.pk)
    if to_status not in ITINERARY_TRANSITIONS.get(locked.status, set()):
        raise ValidationError({"to_status": "This itinerary transition is not allowed."})
    TravelItinerary.objects.filter(pk=locked.pk).update(
        status=to_status,
        archived_at=timezone.now() if to_status == TravelItinerary.Status.ARCHIVED else None,
        updated_at=timezone.now(),
    )
    locked.status = to_status
    audit(
        actor,
        locked.organization,
        "travel.itinerary_status_changed",
        locked,
        "Travel itinerary status changed.",
        request,
    )
    if to_status == TravelItinerary.Status.CONFIRMED:
        notify(
            locked,
            actor=actor,
            notification_type="travel.itinerary_confirmed",
            title="Travel itinerary confirmed",
            message="An itinerary associated with you has been confirmed.",
        )
    return locked


def create_child(model, itinerary, *, actor, data, action, description, request=None):
    require(actor, itinerary.organization, "travel.manage")
    data.pop("status", None)
    item = model(itinerary=itinerary, **data)
    item.save()
    audit(actor, itinerary.organization, action, item, description, request)
    return item


def update_child(item, *, actor, data, action, description, request=None):
    require(actor, item.itinerary.organization, "travel.manage")
    data.pop("status", None)
    data.pop("itinerary", None)
    for key, value in data.items():
        setattr(item, key, value)
    item.save()
    audit(actor, item.itinerary.organization, action, item, description, request)
    return item


def remove_child(item, *, actor, action, description, request=None):
    require(actor, item.itinerary.organization, "travel.manage")
    organization = item.itinerary.organization
    item.delete()
    audit(actor, organization, action, item, description, request)


def transition_child(item, *, actor, to_status, transitions, action, request=None):
    require(actor, item.itinerary.organization, "travel.status.manage")
    with transaction.atomic():
        locked = (
            type(item)
            .objects.select_for_update()
            .select_related("itinerary__organization")
            .get(pk=item.pk)
        )
        if to_status not in transitions.get(locked.status, set()):
            raise ValidationError({"to_status": "This status transition is not allowed."})
        type(item).objects.filter(pk=locked.pk).update(status=to_status, updated_at=timezone.now())
        locked.status = to_status
        audit(
            actor,
            locked.itinerary.organization,
            action,
            locked,
            "Travel item status changed.",
            request,
        )
    return locked


@transaction.atomic
def reorder_segment(segment, *, actor, direction, request=None):
    require(actor, segment.itinerary.organization, "travel.manage")
    step = -1 if direction == "up" else 1
    locked = TravelSegment.objects.select_for_update().get(pk=segment.pk)
    other = (
        TravelSegment.objects.select_for_update()
        .filter(itinerary=locked.itinerary, sequence=locked.sequence + step)
        .first()
    )
    if not other:
        return locked
    original = locked.sequence
    TravelSegment.objects.filter(pk=locked.pk).update(sequence=1000000000)
    TravelSegment.objects.filter(pk=other.pk).update(sequence=original)
    TravelSegment.objects.filter(pk=locked.pk).update(sequence=original + step)
    locked.sequence = original + step
    audit(
        actor,
        locked.itinerary.organization,
        "travel.segment_updated",
        locked,
        "Travel segment order changed.",
        request,
    )
    return locked
