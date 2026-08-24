from django.db import transaction

from audit.services import record_event
from organizations.permissions import user_has_organization_permission

from .models import CalendarEvent


def require(user, organization, permission):
    if not user_has_organization_permission(user, organization, permission):
        raise PermissionError("Permission denied.")


def create_event(*, actor, organization, request=None, **data):
    require(actor, organization, "calendar.manage")
    event = CalendarEvent(organization=organization, created_by=actor, **data)
    event.save()
    record_event(
        actor=actor,
        organization=organization,
        action="calendar.event_created",
        resource=event,
        description="Calendar event created.",
        request=request,
    )
    return event


def update_event(event, *, actor, request=None, **data):
    require(actor, event.organization, "calendar.manage")
    data.pop("status", None)
    for key, value in data.items():
        setattr(event, key, value)
    event.save()
    record_event(
        actor=actor,
        organization=event.organization,
        action="calendar.event_updated",
        resource=event,
        description="Calendar event updated.",
        request=request,
    )
    return event


@transaction.atomic
def transition_event(event, status, *, actor, request=None):
    require(actor, event.organization, "calendar.manage")
    if status not in CalendarEvent.Status.values:
        raise ValueError("Invalid status.")
    locked = CalendarEvent.objects.select_for_update().get(pk=event.pk)
    CalendarEvent.objects.filter(pk=locked.pk).update(status=status)
    locked.status = status
    action = (
        "calendar.event_cancelled"
        if status == CalendarEvent.Status.CANCELLED
        else "calendar.event_archived"
    )
    record_event(
        actor=actor,
        organization=locked.organization,
        action=action,
        resource=locked,
        description=f"Calendar event marked {status}.",
        request=request,
    )
    return locked
