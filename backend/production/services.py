from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from audit.services import record_event
from notifications.models import Notification
from notifications.services import create_notification
from organizations.permissions import user_has_organization_permission

from .models import (
    AdvanceChecklistItem,
    AdvanceRequirement,
    ProductionAdvance,
    ProductionScheduleItem,
)

ADVANCE_TRANSITIONS = {
    "draft": {"in_progress", "cancelled"},
    "in_progress": {"ready", "cancelled"},
    "ready": {"in_progress", "confirmed", "cancelled"},
    "confirmed": {"in_progress", "completed", "cancelled"},
    "completed": {"archived"},
    "cancelled": {"archived"},
    "archived": set(),
}
REQUIREMENT_TRANSITIONS = {
    "open": {"requested", "in_progress", "blocked", "not_applicable"},
    "requested": {"in_progress", "confirmed", "blocked", "not_applicable"},
    "in_progress": {"requested", "confirmed", "blocked", "not_applicable"},
    "blocked": {"in_progress", "requested", "not_applicable"},
    "confirmed": {"in_progress"},
    "not_applicable": {"open"},
}
SCHEDULE_TRANSITIONS = {
    "planned": {"confirmed", "cancelled"},
    "confirmed": {"planned", "cancelled"},
    "cancelled": set(),
}


def require(user, organization, permission):
    if not user_has_organization_permission(user, organization, permission):
        raise PermissionDenied(
            "You do not have permission to manage Production for this organization."
        )


def audit(actor, organization, action, resource, description, request=None):
    record_event(
        actor=actor,
        organization=organization,
        action=action,
        resource=resource,
        description=description,
        request=request,
    )


def create_advance(*, actor, organization, data, request=None):
    require(actor, organization, "production.manage")
    data.pop("status", None)
    booking = data["booking"]
    data["artist"] = booking.artist
    if data.get("venue") is None:
        data["venue"] = booking.venue
    if data.get("promoter") is None:
        data["promoter"] = booking.promoter
    data.setdefault("production_title", f"{booking.title} production")
    row = ProductionAdvance(organization=organization, created_by=actor, **data)
    row.save()
    audit(
        actor,
        organization,
        "production.advance_created",
        row,
        "Production Advance created.",
        request,
    )
    return row


def update_advance(row, *, actor, data, request=None):
    require(actor, row.organization, "production.manage")
    for key in ("status", "organization", "booking", "artist", "created_by"):
        data.pop(key, None)
    for key, value in data.items():
        setattr(row, key, value)
    row.save()
    audit(
        actor,
        row.organization,
        "production.advance_updated",
        row,
        "Production Advance updated.",
        request,
    )
    return row


@transaction.atomic
def transition_advance(row, *, actor, to_status, request=None):
    require(actor, row.organization, "production.status.manage")
    locked = ProductionAdvance.objects.select_for_update().get(pk=row.pk)
    if to_status not in ADVANCE_TRANSITIONS.get(locked.status, set()):
        raise ValidationError({"to_status": "This Production Advance transition is not allowed."})
    now = timezone.now()
    ProductionAdvance.objects.filter(pk=locked.pk).update(
        status=to_status,
        updated_at=now,
        archived_at=now if to_status == "archived" else None,
        last_advanced_at=now if to_status in {"ready", "confirmed"} else locked.last_advanced_at,
    )
    locked.refresh_from_db()
    audit(
        actor,
        locked.organization,
        "production.advance_status_changed",
        locked,
        "Production Advance status changed.",
        request,
    )
    if to_status in {"ready", "confirmed"}:
        assignments = locked.booking.team_assignments.filter(
            is_active=True, membership__is_active=True, membership__user__is_active=True
        ).select_related("membership__user")
        users = [assignment.membership.user for assignment in assignments]
        create_notification(
            organization=locked.organization,
            notification_type=f"production.advance_{to_status}",
            category=Notification.Category.BOOKINGS,
            title=f"Production Advance {to_status}",
            message=f"Production preparation for {locked.booking.reference} is {to_status}.",
            users=users,
            actor=actor,
            source=locked,
            action_url=f"/workspace/production/{locked.pk}",
        )
    return locked


@transaction.atomic
def create_child(model, advance, *, actor, data, permission, action, request=None):
    require(actor, advance.organization, permission)
    if model in (AdvanceRequirement, ProductionScheduleItem, AdvanceChecklistItem):
        locked_advance = ProductionAdvance.objects.select_for_update().get(pk=advance.pk)
        maximum = model.objects.filter(advance=locked_advance, is_active=True).aggregate(
            maximum=Max("sequence")
        )["maximum"]
        data["sequence"] = (maximum or 0) + 1
    if model in (AdvanceRequirement, ProductionScheduleItem):
        data.pop("status", None)
    if hasattr(model, "created_by"):
        data.setdefault("created_by", actor)
    row = model(advance=advance, **data)
    row.save()
    audit(actor, advance.organization, action, row, action.replace(".", " ").title() + ".", request)
    if data.get("assigned_membership") and action in {
        "production.requirement_created",
        "production.checklist_created",
    }:
        member = data["assigned_membership"]
        create_notification(
            organization=advance.organization,
            notification_type=action.replace("_created", "_assigned"),
            category=Notification.Category.BOOKINGS,
            title="Production work assigned",
            message=f"Production work was assigned for {advance.booking.reference}.",
            users=[member.user],
            actor=actor,
            source=advance,
            action_url=f"/workspace/production/{advance.pk}",
        )
    return row


def update_child(row, *, actor, data, permission, action, request=None):
    require(actor, row.advance.organization, permission)
    data.pop("advance", None)
    if isinstance(row, AdvanceRequirement | ProductionScheduleItem):
        data.pop("status", None)
    if isinstance(row, AdvanceChecklistItem):
        for key in ("is_completed", "completed_by", "completed_at"):
            data.pop(key, None)
    for key, value in data.items():
        setattr(row, key, value)
    row.save()
    audit(actor, row.advance.organization, action, row, "Production item updated.", request)
    return row


def deactivate_child(row, *, actor, permission, action, request=None):
    require(actor, row.advance.organization, permission)
    row.is_active = False
    row.save(update_fields=("is_active", "updated_at"))
    audit(actor, row.advance.organization, action, row, "Production item removed.", request)


@transaction.atomic
def transition_child(row, *, actor, to_status, permission, transitions, action, request=None):
    require(actor, row.advance.organization, permission)
    locked = type(row).objects.select_for_update().get(pk=row.pk)
    if to_status not in transitions.get(locked.status, set()):
        raise ValidationError({"to_status": "This status transition is not allowed."})
    values = {"status": to_status, "updated_at": timezone.now()}
    if isinstance(locked, AdvanceRequirement):
        values["completed_at"] = (
            timezone.now() if to_status in {"confirmed", "not_applicable"} else None
        )
    type(row).objects.filter(pk=locked.pk).update(**values)
    locked.refresh_from_db()
    audit(
        actor,
        locked.advance.organization,
        action,
        locked,
        "Production item status changed.",
        request,
    )
    return locked


@transaction.atomic
def set_checklist_completion(row, *, actor, completed, request=None):
    require(actor, row.advance.organization, "production.checklist.manage")
    locked = AdvanceChecklistItem.objects.select_for_update().get(pk=row.pk)
    if locked.is_completed == completed:
        raise ValidationError("Checklist item is already in this state.")
    now = timezone.now()
    AdvanceChecklistItem.objects.filter(pk=locked.pk).update(
        is_completed=completed,
        completed_by=actor if completed else None,
        completed_at=now if completed else None,
        updated_at=now,
    )
    locked.refresh_from_db()
    audit(
        actor,
        locked.advance.organization,
        "production.checklist_completed" if completed else "production.checklist_reopened",
        locked,
        "Production checklist state changed.",
        request,
    )
    return locked


@transaction.atomic
def reorder_child(row, *, actor, direction, permission, action, request=None):
    require(actor, row.advance.organization, permission)
    step = -1 if direction == "up" else 1
    locked = type(row).objects.select_for_update().get(pk=row.pk)
    other = (
        type(row)
        .objects.select_for_update()
        .filter(
            advance_id=locked.advance_id,
            is_active=True,
            sequence=locked.sequence + step,
        )
        .first()
    )
    if not other:
        return locked
    original = locked.sequence
    type(row).objects.filter(pk=locked.pk).update(sequence=1000000000)
    type(row).objects.filter(pk=other.pk).update(sequence=original)
    type(row).objects.filter(pk=locked.pk).update(sequence=original + step)
    locked.sequence = original + step
    audit(
        actor,
        locked.advance.organization,
        action,
        locked,
        "Production item order changed.",
        request,
    )
    return locked
