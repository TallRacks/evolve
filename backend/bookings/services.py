from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from audit.services import record_event
from notifications.services import booking_team_users, create_notification
from organizations.permissions import user_has_organization_permission

from .models import (
    Booking,
    BookingContactAssignment,
    BookingStatusHistory,
    BookingTeamAssignment,
)

ALLOWED_TRANSITIONS = {
    Booking.Status.ENQUIRY: {Booking.Status.HOLD, Booking.Status.PENDING, Booking.Status.DECLINED},
    Booking.Status.HOLD: {
        Booking.Status.PENDING,
        Booking.Status.CONFIRMED,
        Booking.Status.CANCELLED,
    },
    Booking.Status.PENDING: {
        Booking.Status.CONFIRMED,
        Booking.Status.DECLINED,
        Booking.Status.CANCELLED,
    },
    Booking.Status.CONFIRMED: {Booking.Status.COMPLETED, Booking.Status.CANCELLED},
    Booking.Status.COMPLETED: set(),
    Booking.Status.CANCELLED: set(),
    Booking.Status.DECLINED: set(),
}

COMMERCIAL_FIELDS = {
    "currency",
    "performance_fee",
    "deposit_amount",
    "deposit_due_date",
    "balance_due_date",
}


def require_booking_permission(actor, organization, permission):
    if getattr(actor, "is_active", False) and getattr(actor, "is_superuser", False):
        return
    if not user_has_organization_permission(actor, organization, permission):
        raise PermissionDenied("You do not have permission for this booking.")


def apply_partner_snapshots(booking, *, promoter_changed=True, venue_changed=True):
    if promoter_changed:
        booking.promoter_name_snapshot = booking.promoter.name if booking.promoter else ""
    if venue_changed:
        booking.venue_name_snapshot = booking.venue.name if booking.venue else ""
        booking.city_snapshot = booking.venue.city if booking.venue else ""
        booking.country_snapshot = booking.venue.country if booking.venue else ""


def allowed_transitions(booking):
    return sorted(ALLOWED_TRANSITIONS[booking.status])


def validate_transition(from_status, to_status):
    if to_status not in ALLOWED_TRANSITIONS[from_status]:
        raise ValidationError(f"Status cannot change from {from_status} to {to_status}.")


@transaction.atomic
def create_booking(*, actor, organization, data, request=None):
    require_booking_permission(actor, organization, "booking.manage")
    sensitive_commercial = {
        field for field in COMMERCIAL_FIELDS if data.get(field) not in (None, "")
    }
    if sensitive_commercial:
        require_booking_permission(actor, organization, "booking.commercial.manage")
    booking = Booking(organization=organization, created_by=actor, **data)
    apply_partner_snapshots(booking)
    booking.full_clean()
    booking.save()
    record_event(
        actor=actor,
        organization=organization,
        action="booking.created",
        resource=booking,
        description=f"Created booking {booking.reference}.",
        request=request,
    )
    return booking


@transaction.atomic
def update_booking(*, actor, booking, data, request=None):
    require_booking_permission(actor, booking.organization, "booking.manage")
    if "status" in data:
        raise ValidationError("Use the booking status transition operation.")
    commercial_changed = COMMERCIAL_FIELDS.intersection(data)
    if commercial_changed:
        require_booking_permission(actor, booking.organization, "booking.commercial.manage")
    promoter_changed = "promoter" in data and data["promoter"] != booking.promoter
    venue_changed = "venue" in data and data["venue"] != booking.venue
    for field, value in data.items():
        setattr(booking, field, value)
    apply_partner_snapshots(booking, promoter_changed=promoter_changed, venue_changed=venue_changed)
    booking.full_clean()
    booking.save()
    description = f"Updated booking {booking.reference}."
    if commercial_changed:
        changed_fields = ", ".join(sorted(commercial_changed))
        description = (
            f"Updated booking {booking.reference}; commercial fields changed: {changed_fields}."
        )
    record_event(
        actor=actor,
        organization=booking.organization,
        action="booking.updated",
        resource=booking,
        description=description,
        request=request,
    )
    return booking


@transaction.atomic
def transition_booking(*, actor, booking, to_status, reason="", request=None):
    require_booking_permission(actor, booking.organization, "booking.status.manage")
    locked = Booking.objects.select_for_update().get(pk=booking.pk)
    validate_transition(locked.status, to_status)
    previous = locked.status
    locked.status = to_status
    locked.full_clean()
    locked.save(update_fields=("status", "updated_at"))
    BookingStatusHistory.objects.create(
        booking=locked,
        from_status=previous,
        to_status=to_status,
        changed_by=actor,
        reason=reason,
    )
    action = {
        Booking.Status.CANCELLED: "booking.cancelled",
        Booking.Status.COMPLETED: "booking.completed",
    }.get(to_status, "booking.status_changed")
    record_event(
        actor=actor,
        organization=locked.organization,
        action=action,
        resource=locked,
        description=f"Changed booking {locked.reference} status from {previous} to {to_status}.",
        request=request,
    )
    create_notification(
        organization=locked.organization,
        notification_type="booking.status_changed",
        category="bookings",
        title="Booking status changed",
        message=f"{locked.reference} is now {to_status}.",
        users=booking_team_users(locked),
        actor=actor,
        priority="high"
        if to_status in (Booking.Status.CONFIRMED, Booking.Status.CANCELLED)
        else "normal",
        source=locked,
        action_url=f"/workspace/bookings/{locked.pk}",
    )
    return locked


@transaction.atomic
def assign_team_member(*, actor, booking, membership, data, request=None):
    require_booking_permission(actor, booking.organization, "booking.team.manage")
    assignment = (
        BookingTeamAssignment.objects.select_for_update()
        .filter(booking=booking, membership=membership)
        .first()
    )
    if assignment and assignment.is_active:
        raise ValidationError("This membership is already assigned to the booking.")
    if assignment:
        assignment.responsibility = data["responsibility"]
        assignment.is_primary = data.get("is_primary", False)
        assignment.is_active = True
    else:
        assignment = BookingTeamAssignment(booking=booking, membership=membership, **data)
    assignment.full_clean()
    assignment.save()
    record_event(
        actor=actor,
        organization=booking.organization,
        action="booking.team_assigned",
        resource=booking,
        description=f"Assigned a team member to booking {booking.reference}.",
        request=request,
    )
    return assignment


@transaction.atomic
def update_team_assignment(*, actor, assignment, data, request=None):
    require_booking_permission(actor, assignment.booking.organization, "booking.team.manage")
    was_active = assignment.is_active
    for field, value in data.items():
        setattr(assignment, field, value)
    assignment.full_clean()
    assignment.save()
    action = (
        "booking.team_removed"
        if was_active and not assignment.is_active
        else "booking.team_updated"
    )
    record_event(
        actor=actor,
        organization=assignment.booking.organization,
        action=action,
        resource=assignment.booking,
        description=f"Updated a team assignment for booking {assignment.booking.reference}.",
        request=request,
    )
    return assignment


@transaction.atomic
def assign_contact(*, actor, booking, contact, data, request=None):
    require_booking_permission(actor, booking.organization, "booking.manage")
    assignment = (
        BookingContactAssignment.objects.select_for_update()
        .filter(booking=booking, contact=contact, responsibility=data["responsibility"])
        .first()
    )
    if assignment and assignment.is_active:
        raise ValidationError("This contact is already assigned for that responsibility.")
    if assignment:
        assignment.is_primary = data.get("is_primary", False)
        assignment.is_active = True
    else:
        assignment = BookingContactAssignment(
            booking=booking,
            contact=contact,
            snapshot_name=contact.full_name,
            snapshot_email=contact.email,
            snapshot_phone=contact.phone or contact.mobile,
            **data,
        )
    assignment.full_clean()
    assignment.save()
    record_event(
        actor=actor,
        organization=booking.organization,
        action="booking.contact_added",
        resource=booking,
        description=f"Added a contact assignment to booking {booking.reference}.",
        request=request,
    )
    return assignment


@transaction.atomic
def update_contact_assignment(*, actor, assignment, data, request=None):
    require_booking_permission(actor, assignment.booking.organization, "booking.manage")
    was_active = assignment.is_active
    for field, value in data.items():
        setattr(assignment, field, value)
    assignment.full_clean()
    assignment.save()
    action = (
        "booking.contact_removed"
        if was_active and not assignment.is_active
        else "booking.contact_updated"
    )
    record_event(
        actor=actor,
        organization=assignment.booking.organization,
        action=action,
        resource=assignment.booking,
        description=f"Updated a contact assignment for booking {assignment.booking.reference}.",
        request=request,
    )
    return assignment
