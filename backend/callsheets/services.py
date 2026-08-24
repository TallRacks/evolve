from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from audit.services import record_event
from bookings.models import Booking
from organizations.permissions import user_has_organization_permission

from .models import (
    CallSheet,
    CallSheetAccommodationItem,
    CallSheetContactEntry,
    CallSheetScheduleItem,
    CallSheetTeamEntry,
    CallSheetTravelItem,
    CallSheetVersion,
)

BOOKING_SNAPSHOT_FIELDS = {
    "event_name",
    "artist_name",
    "event_date",
    "event_start_datetime",
    "event_end_datetime",
    "timezone",
    "venue_name",
    "venue_address",
    "city",
    "province",
    "country",
    "venue_phone",
    "promoter_name",
}


def require_callsheet_permission(actor, organization, permission):
    if getattr(actor, "is_active", False) and getattr(actor, "is_superuser", False):
        return
    if not user_has_organization_permission(actor, organization, permission):
        raise PermissionDenied("You do not have permission for this Call Sheet.")


def booking_snapshot(booking):
    venue = booking.venue
    address = ""
    if venue:
        address = ", ".join(
            value
            for value in (
                venue.address_line_1,
                venue.address_line_2,
                venue.city,
                venue.province,
                venue.postal_code,
                venue.country,
            )
            if value
        )
    return {
        "event_name": booking.title,
        "artist_name": booking.artist.stage_name,
        "event_date": booking.event_date,
        "event_start_datetime": booking.event_start_datetime,
        "event_end_datetime": booking.event_end_datetime,
        "timezone": booking.timezone,
        "venue_name": booking.venue_name_snapshot,
        "venue_address": address,
        "city": booking.city_snapshot,
        "province": venue.province if venue else "",
        "country": booking.country_snapshot,
        "venue_phone": venue.public_phone if venue else "",
        "promoter_name": booking.promoter_name_snapshot,
    }


def ensure_editable(version):
    if not version.is_editable:
        raise ValidationError("This Call Sheet version is immutable. Create a new draft.")


def _copy_children(source, target):
    models_and_fields = (
        (
            CallSheetScheduleItem,
            "schedule_items",
            (
                "sequence",
                "start_time",
                "end_time",
                "title",
                "description",
                "location",
                "responsibility",
                "is_highlighted",
            ),
        ),
        (
            CallSheetTeamEntry,
            "team_entries",
            (
                "sequence",
                "booking_team_assignment",
                "membership",
                "name_snapshot",
                "role_snapshot",
                "responsibility_snapshot",
                "phone_snapshot",
                "email_snapshot",
                "call_time",
                "notes",
            ),
        ),
        (
            CallSheetContactEntry,
            "contact_entries",
            (
                "sequence",
                "source_contact",
                "responsibility",
                "name_snapshot",
                "company_snapshot",
                "email_snapshot",
                "phone_snapshot",
                "notes",
                "is_primary",
            ),
        ),
        (
            CallSheetTravelItem,
            "travel_items",
            (
                "sequence",
                "type",
                "provider",
                "reference",
                "departure_location",
                "arrival_location",
                "departure_datetime",
                "arrival_datetime",
                "traveler_notes",
                "contact_name",
                "contact_phone",
                "notes",
            ),
        ),
        (
            CallSheetAccommodationItem,
            "accommodation_items",
            (
                "sequence",
                "property_name",
                "address",
                "check_in_datetime",
                "check_out_datetime",
                "confirmation_reference",
                "contact_name",
                "contact_phone",
                "notes",
            ),
        ),
    )
    for model, relation, fields in models_and_fields:
        model.objects.bulk_create(
            [
                model(version=target, **{field: getattr(item, field) for field in fields})
                for item in getattr(source, relation).all()
            ]
        )


def _populate_booking_people(version):
    booking = version.call_sheet.booking
    for sequence, assignment in enumerate(
        booking.team_assignments.filter(is_active=True).select_related("membership__user"), 1
    ):
        user = assignment.membership.user
        CallSheetTeamEntry.objects.create(
            version=version,
            sequence=sequence,
            booking_team_assignment=assignment,
            membership=assignment.membership,
            name_snapshot=f"{user.first_name} {user.last_name}".strip() or user.email,
            role_snapshot=assignment.membership.get_role_display(),
            responsibility_snapshot=assignment.get_responsibility_display(),
            email_snapshot=user.email,
        )
    for sequence, assignment in enumerate(
        booking.contact_assignments.filter(is_active=True).select_related("contact"), 1
    ):
        CallSheetContactEntry.objects.create(
            version=version,
            sequence=sequence,
            source_contact=assignment.contact,
            responsibility=assignment.get_responsibility_display(),
            name_snapshot=assignment.snapshot_name,
            email_snapshot=assignment.snapshot_email,
            phone_snapshot=assignment.snapshot_phone,
            is_primary=assignment.is_primary,
        )


@transaction.atomic
def create_call_sheet(*, actor, booking, request=None):
    require_callsheet_permission(actor, booking.organization, "callsheet.manage")
    call_sheet = CallSheet(organization=booking.organization, booking=booking, created_by=actor)
    call_sheet.full_clean()
    call_sheet.save()
    record_event(
        actor=actor,
        organization=booking.organization,
        action="callsheet.created",
        resource=call_sheet,
        description=f"Created Call Sheet for booking {booking.reference}.",
        request=request,
    )
    version = create_call_sheet_version(actor=actor, call_sheet=call_sheet, request=request)
    return call_sheet, version


@transaction.atomic
def create_call_sheet_version(*, actor, call_sheet, source_version=None, request=None):
    require_callsheet_permission(actor, call_sheet.organization, "callsheet.manage")
    locked = CallSheet.objects.select_for_update().get(pk=call_sheet.pk)
    booking = (
        Booking.objects.select_related("artist", "venue", "promoter")
        .prefetch_related(
            "team_assignments__membership__user",
            "contact_assignments__contact",
        )
        .get(pk=locked.booking_id)
    )
    locked.booking = booking
    number = (locked.versions.aggregate(latest=Max("version_number"))["latest"] or 0) + 1
    snapshot = booking_snapshot(booking)
    values = {
        **snapshot,
        "title": f"{booking.artist.stage_name} - {booking.title}",
    }
    if source_version:
        if source_version.call_sheet_id != locked.id:
            raise ValidationError("Source version must belong to this Call Sheet.")
        copy_fields = [
            field.name
            for field in CallSheetVersion._meta.fields
            if field.name
            not in {
                "id",
                "call_sheet",
                "version_number",
                "status",
                "created_by",
                "published_by",
                "published_at",
                "superseded_at",
                "created_at",
                "updated_at",
            }
        ]
        values = {field: getattr(source_version, field) for field in copy_fields}
    version = CallSheetVersion(
        call_sheet=locked,
        version_number=number,
        created_by=actor,
        status=CallSheetVersion.Status.DRAFT,
        **values,
    )
    version.full_clean()
    version.save()
    if source_version:
        _copy_children(source_version, version)
    else:
        _populate_booking_people(version)
    record_event(
        actor=actor,
        organization=locked.organization,
        action="callsheet.version_created",
        resource=version,
        description=f"Created Call Sheet version {number} for booking {locked.booking.reference}.",
        request=request,
    )
    return version


@transaction.atomic
def update_version(*, actor, version, data, request=None):
    require_callsheet_permission(actor, version.call_sheet.organization, "callsheet.manage")
    ensure_editable(version)
    if "status" in data:
        raise ValidationError("Use a Call Sheet lifecycle operation.")
    for field, value in data.items():
        setattr(version, field, value)
    version.full_clean()
    version.save()
    record_event(
        actor=actor,
        organization=version.call_sheet.organization,
        action="callsheet.updated",
        resource=version,
        description=f"Updated Call Sheet version {version.version_number}.",
        request=request,
    )
    sections = {
        "callsheet.production_updated": {
            "soundcheck_time",
            "production_contact",
            "stage_notes",
            "technical_notes",
            "backline_notes",
            "special_requirements",
        },
        "callsheet.hospitality_updated": {
            "catering_notes",
            "dietary_notes",
            "guest_notes",
            "dressing_room_notes",
        },
    }
    for action, fields in sections.items():
        if fields.intersection(data):
            record_event(
                actor=actor,
                organization=version.call_sheet.organization,
                action=action,
                resource=version,
                description=f"Updated Call Sheet version {version.version_number}.",
                request=request,
            )
    return version


@transaction.atomic
def refresh_from_booking(*, actor, version, request=None):
    require_callsheet_permission(actor, version.call_sheet.organization, "callsheet.manage")
    if version.status != CallSheetVersion.Status.DRAFT:
        raise ValidationError("Only draft Call Sheet versions can refresh from Booking.")
    version.call_sheet.booking.refresh_from_db()
    for field, value in booking_snapshot(version.call_sheet.booking).items():
        setattr(version, field, value)
    version.full_clean()
    version.save()
    record_event(
        actor=actor,
        organization=version.call_sheet.organization,
        action="callsheet.refreshed_from_booking",
        resource=version,
        description=f"Refreshed Call Sheet version {version.version_number} from Booking.",
        request=request,
    )
    return version


@transaction.atomic
def mark_ready(*, actor, version, request=None):
    require_callsheet_permission(actor, version.call_sheet.organization, "callsheet.manage")
    locked = CallSheetVersion.objects.select_for_update().get(pk=version.pk)
    if locked.status != CallSheetVersion.Status.DRAFT:
        raise ValidationError("Only a draft Call Sheet can be marked ready.")
    CallSheetVersion.objects.filter(pk=locked.pk).update(
        status=CallSheetVersion.Status.READY, updated_at=timezone.now()
    )
    locked.refresh_from_db()
    record_event(
        actor=actor,
        organization=locked.call_sheet.organization,
        action="callsheet.ready",
        resource=locked,
        description=f"Marked Call Sheet version {locked.version_number} ready.",
        request=request,
    )
    return locked


@transaction.atomic
def publish_call_sheet_version(*, actor, version, request=None):
    require_callsheet_permission(actor, version.call_sheet.organization, "callsheet.publish")
    CallSheet.objects.select_for_update().get(pk=version.call_sheet_id)
    locked = CallSheetVersion.objects.select_for_update().get(pk=version.pk)
    if locked.status != CallSheetVersion.Status.READY:
        raise ValidationError("Only a ready Call Sheet can be published.")
    now = timezone.now()
    previous = (
        CallSheetVersion.objects.select_for_update()
        .filter(call_sheet=locked.call_sheet, status=CallSheetVersion.Status.PUBLISHED)
        .exclude(pk=locked.pk)
        .first()
    )
    if previous:
        CallSheetVersion.objects.filter(pk=previous.pk).update(
            status=CallSheetVersion.Status.SUPERSEDED, superseded_at=now, updated_at=now
        )
        record_event(
            actor=actor,
            organization=locked.call_sheet.organization,
            action="callsheet.superseded",
            resource=previous,
            description=f"Superseded Call Sheet version {previous.version_number}.",
            request=request,
        )
    CallSheetVersion.objects.filter(pk=locked.pk).update(
        status=CallSheetVersion.Status.PUBLISHED,
        published_by=actor,
        published_at=now,
        updated_at=now,
    )
    locked.refresh_from_db()
    record_event(
        actor=actor,
        organization=locked.call_sheet.organization,
        action="callsheet.published",
        resource=locked,
        description=f"Published Call Sheet version {locked.version_number}.",
        request=request,
    )
    return locked


@transaction.atomic
def cancel_version(*, actor, version, request=None):
    require_callsheet_permission(actor, version.call_sheet.organization, "callsheet.manage")
    locked = CallSheetVersion.objects.select_for_update().get(pk=version.pk)
    if locked.status not in {CallSheetVersion.Status.DRAFT, CallSheetVersion.Status.READY}:
        raise ValidationError("Only draft or ready versions can be cancelled.")
    CallSheetVersion.objects.filter(pk=locked.pk).update(
        status=CallSheetVersion.Status.CANCELLED, updated_at=timezone.now()
    )
    locked.refresh_from_db()
    record_event(
        actor=actor,
        organization=locked.call_sheet.organization,
        action="callsheet.cancelled",
        resource=locked,
        description=f"Cancelled Call Sheet version {locked.version_number}.",
        request=request,
    )
    return locked


@transaction.atomic
def create_child(*, actor, version, model, data, action, request=None):
    require_callsheet_permission(actor, version.call_sheet.organization, "callsheet.manage")
    ensure_editable(version)
    child = model(version=version, **data)
    child.full_clean()
    child.save()
    record_event(
        actor=actor,
        organization=version.call_sheet.organization,
        action=action,
        resource=version,
        description=f"Updated Call Sheet version {version.version_number}.",
        request=request,
    )
    return child


@transaction.atomic
def update_child(*, actor, child, data, action, request=None):
    require_callsheet_permission(actor, child.version.call_sheet.organization, "callsheet.manage")
    ensure_editable(child.version)
    for field, value in data.items():
        setattr(child, field, value)
    child.full_clean()
    child.save()
    record_event(
        actor=actor,
        organization=child.version.call_sheet.organization,
        action=action,
        resource=child.version,
        description=f"Updated Call Sheet version {child.version.version_number}.",
        request=request,
    )
    return child


@transaction.atomic
def remove_child(*, actor, child, action, request=None):
    require_callsheet_permission(actor, child.version.call_sheet.organization, "callsheet.manage")
    ensure_editable(child.version)
    version = child.version
    child.delete()
    record_event(
        actor=actor,
        organization=version.call_sheet.organization,
        action=action,
        resource=version,
        description=f"Updated Call Sheet version {version.version_number}.",
        request=request,
    )
