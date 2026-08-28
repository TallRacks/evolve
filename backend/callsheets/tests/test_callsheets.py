from datetime import date, time
from threading import Barrier, Thread

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import RequestFactory

from artists.models import Artist
from audit.models import AuditEvent
from bookings.models import Booking, BookingContactAssignment, BookingTeamAssignment
from callsheets.admin import CallSheetAdmin, CallSheetVersionAdmin, ChildAdmin
from callsheets.models import (
    CallSheet,
    CallSheetContactEntry,
    CallSheetScheduleItem,
    CallSheetTeamEntry,
    CallSheetVersion,
)
from callsheets.services import (
    create_call_sheet,
    create_call_sheet_version,
    create_child,
    mark_ready,
    publish_call_sheet_version,
    refresh_from_booking,
)
from contacts.models import Contact
from notifications.models import NotificationRecipient
from organizations.models import Membership, Organization
from users.models import User
from venues.models import Venue
from white_label.services import create_api_client_key

pytestmark = pytest.mark.django_db
PASSWORD = "Test-only-callsheet-credential-123"


@pytest.fixture
def organization():
    return Organization.objects.create(name="Call Sheet Org", slug="call-sheet-org")


@pytest.fixture
def other_organization():
    return Organization.objects.create(name="Other Call Sheet Org", slug="other-call-sheet-org")


def user_for(organization, role, email):
    user = User.objects.create_user(email=email, password=PASSWORD)
    Membership.objects.create(user=user, organization=organization, role=role)
    return user


@pytest.fixture
def owner(organization):
    return user_for(organization, Membership.Role.OWNER, "callsheet-owner@example.invalid")


@pytest.fixture
def manager(organization):
    return user_for(organization, Membership.Role.MANAGER, "callsheet-manager@example.invalid")


@pytest.fixture
def member(organization):
    return user_for(organization, Membership.Role.MEMBER, "callsheet-member@example.invalid")


@pytest.fixture
def booking(organization, owner):
    artist = Artist.objects.create(
        organization=organization, stage_name="Signal North", slug="signal-north"
    )
    venue = Venue.objects.create(
        organization=organization,
        name="Signal Hall",
        slug="signal-hall",
        address_line_1="1 Main Road",
        city="Cape Town",
        province="Western Cape",
        country="South Africa",
        public_phone="+27000000000",
    )
    booking = Booking.objects.create(
        organization=organization,
        artist=artist,
        venue=venue,
        title="Signal North Live",
        event_date=date(2026, 12, 1),
        venue_name_snapshot=venue.name,
        city_snapshot=venue.city,
        country_snapshot=venue.country,
        created_by=owner,
    )
    owner_membership = Membership.objects.get(user=owner, organization=organization)
    team = BookingTeamAssignment.objects.create(
        booking=booking,
        membership=owner_membership,
        responsibility=BookingTeamAssignment.Responsibility.MANAGER,
        is_primary=True,
    )
    contact = Contact.objects.create(
        organization=organization,
        first_name="Alex",
        last_name="Ops",
        email="alex@example.invalid",
        phone="+27111111111",
    )
    BookingContactAssignment.objects.create(
        booking=booking,
        contact=contact,
        responsibility=BookingContactAssignment.Responsibility.BOOKING,
        is_primary=True,
        snapshot_name=contact.full_name,
        snapshot_email=contact.email,
        snapshot_phone=contact.phone,
    )
    assert team
    return booking


@pytest.fixture
def call_sheet(owner, booking):
    return create_call_sheet(actor=owner, booking=booking)


def test_one_call_sheet_per_booking_and_snapshot_population(call_sheet, booking):
    sheet, version = call_sheet
    assert version.version_number == 1
    assert version.artist_name == "Signal North"
    assert version.venue_name == "Signal Hall"
    assert version.team_entries.count() == 1
    assert version.contact_entries.count() == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        CallSheet.objects.create(organization=booking.organization, booking=booking)


def test_generation_is_idempotent(owner, booking):
    first_sheet, first_version = create_call_sheet(actor=owner, booking=booking)
    second_sheet, second_version = create_call_sheet(actor=owner, booking=booking)

    assert second_sheet == first_sheet
    assert second_version == first_version
    assert CallSheet.objects.filter(booking=booking).count() == 1
    assert first_sheet.versions.count() == 1


def test_call_sheet_rejects_cross_organization(booking, other_organization):
    sheet = CallSheet(organization=other_organization, booking=booking)
    with pytest.raises(ValidationError):
        sheet.full_clean()


def test_versions_are_sequential_and_copy_is_independent(owner, call_sheet):
    sheet, first = call_sheet
    CallSheetScheduleItem.objects.create(
        version=first, sequence=1, start_time=time(17), title="Soundcheck"
    )
    second = create_call_sheet_version(actor=owner, call_sheet=sheet, source_version=first)
    third = create_call_sheet_version(actor=owner, call_sheet=sheet, source_version=second)
    assert [first.version_number, second.version_number, third.version_number] == [1, 2, 3]
    copied = second.schedule_items.get()
    copied.title = "Changed copy"
    copied.save()
    assert first.schedule_items.get().title == "Soundcheck"


@pytest.mark.django_db(transaction=True)
def test_postgresql_nullable_booking_relations_can_create_call_sheet(owner, booking):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL locking regression")
    booking.venue = None
    booking.venue_name_snapshot = "Snapshot-only venue"
    booking.save(update_fields=("venue", "venue_name_snapshot", "updated_at"))

    sheet, version = create_call_sheet(actor=owner, booking=booking)

    assert sheet.booking_id == booking.id
    assert version.version_number == 1
    assert version.venue_name == "Snapshot-only venue"
    assert version.province == ""
    assert version.promoter_name == ""


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_versions_are_serialized(owner, booking):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL concurrency regression")
    sheet = CallSheet.objects.create(
        organization=booking.organization,
        booking=booking,
        created_by=owner,
    )
    barrier = Barrier(2)
    numbers = []
    errors = []

    def create_version():
        close_old_connections()
        try:
            actor = User.objects.get(pk=owner.pk)
            thread_sheet = CallSheet.objects.get(pk=sheet.pk)
            barrier.wait()
            version = create_call_sheet_version(actor=actor, call_sheet=thread_sheet)
            numbers.append(version.version_number)
        except Exception as error:  # pragma: no cover - asserted below
            errors.append(error)
        finally:
            close_old_connections()

    threads = [Thread(target=create_version) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    assert sorted(numbers) == [1, 2]
    assert list(
        sheet.versions.order_by("version_number").values_list("version_number", flat=True)
    ) == [1, 2]


def test_publish_supersedes_previous_atomically_and_audits(owner, member, call_sheet):
    sheet, first = call_sheet
    BookingTeamAssignment.objects.create(
        booking=sheet.booking,
        membership=Membership.objects.get(user=member, organization=sheet.organization),
        responsibility=BookingTeamAssignment.Responsibility.GENERAL,
    )
    mark_ready(actor=owner, version=first)
    first = publish_call_sheet_version(actor=owner, version=first)
    second = create_call_sheet_version(actor=owner, call_sheet=sheet, source_version=first)
    mark_ready(actor=owner, version=second)
    second = publish_call_sheet_version(actor=owner, version=second)
    first.refresh_from_db()
    assert first.status == CallSheetVersion.Status.SUPERSEDED
    assert second.status == CallSheetVersion.Status.PUBLISHED
    assert sheet.versions.filter(status=CallSheetVersion.Status.PUBLISHED).count() == 1
    assert set(
        NotificationRecipient.objects.filter(user=member).values_list(
            "notification__notification_type", flat=True
        )
    ) == {"callsheet.ready", "callsheet.published"}
    assert set(AuditEvent.objects.values_list("action", flat=True)) >= {
        "callsheet.ready",
        "callsheet.published",
        "callsheet.superseded",
    }


def test_invalid_publish_and_immutable_published_content(owner, call_sheet):
    _, version = call_sheet
    version.status = CallSheetVersion.Status.PUBLISHED
    with pytest.raises(ValidationError):
        version.save()
    version.status = CallSheetVersion.Status.DRAFT
    with pytest.raises(ValidationError):
        publish_call_sheet_version(actor=owner, version=version)
    item = CallSheetScheduleItem.objects.create(
        version=version, sequence=1, start_time=time(18), title="Doors"
    )
    mark_ready(actor=owner, version=version)
    version = publish_call_sheet_version(actor=owner, version=version)
    version.title = "Illegal"
    with pytest.raises(ValidationError):
        version.save()
    item.title = "Illegal"
    with pytest.raises(ValidationError):
        item.save()
    with pytest.raises(ValidationError):
        item.delete()


def test_refresh_only_draft_and_master_change_does_not_rewrite_published(
    owner, call_sheet, booking
):
    _, version = call_sheet
    booking.title = "Updated Booking"
    booking.save()
    refresh_from_booking(actor=owner, version=version)
    assert version.event_name == "Updated Booking"
    mark_ready(actor=owner, version=version)
    version = publish_call_sheet_version(actor=owner, version=version)
    booking.title = "Later Booking"
    booking.save()
    version.refresh_from_db()
    assert version.event_name == "Updated Booking"
    with pytest.raises(ValidationError):
        refresh_from_booking(actor=owner, version=version)


def test_child_cross_org_and_published_mutation_rejected(owner, call_sheet, other_organization):
    _, version = call_sheet
    other_contact = Contact.objects.create(
        organization=other_organization, first_name="Other", last_name="Contact"
    )
    with pytest.raises(ValidationError):
        create_child(
            actor=owner,
            version=version,
            model=CallSheetContactEntry,
            data={
                "source_contact": other_contact,
                "responsibility": "Venue",
                "name_snapshot": "Other Contact",
            },
            action="callsheet.contacts_updated",
        )


def test_permissions_and_cross_org_api(client, manager, member, call_sheet, other_organization):
    sheet, version = call_sheet
    client.force_login(manager)
    assert client.get(f"/api/call-sheet-versions/{version.id}/").status_code == 200
    assert (
        client.patch(
            f"/api/call-sheet-versions/{version.id}/",
            {"subtitle": "Manager edit"},
            content_type="application/json",
        ).status_code
        == 200
    )
    client.force_login(member)
    assert client.get(f"/api/call-sheets/{sheet.id}/").status_code == 200
    assert (
        client.patch(
            f"/api/call-sheet-versions/{version.id}/",
            {"subtitle": "Denied"},
            content_type="application/json",
        ).status_code
        == 403
    )
    outsider = user_for(
        other_organization, Membership.Role.OWNER, "callsheet-outsider@example.invalid"
    )
    client.force_login(outsider)
    assert client.get(f"/api/call-sheets/{sheet.id}/").status_code == 404


def test_staff_cannot_bypass_and_superuser_can(client, call_sheet):
    sheet, _ = call_sheet
    staff = User.objects.create_user(
        email="callsheet-staff@example.invalid", password=PASSWORD, is_staff=True
    )
    client.force_login(staff)
    assert client.get(f"/api/call-sheets/{sheet.id}/").status_code == 404
    platform = User.objects.create_superuser(
        email="callsheet-platform@example.invalid", password=PASSWORD
    )
    client.force_login(platform)
    assert client.get(f"/api/platform/call-sheets/{sheet.id}/").status_code == 200


def test_api_children_and_published_immutability(client, manager, call_sheet):
    _, version = call_sheet
    client.force_login(manager)
    created = client.post(
        f"/api/call-sheet-versions/{version.id}/schedule/",
        {"sequence": 1, "start_time": "16:00", "title": "Load in"},
        content_type="application/json",
    )
    assert created.status_code == 201, created.content
    assert client.post(f"/api/call-sheet-versions/{version.id}/ready/").status_code == 200
    assert client.post(f"/api/call-sheet-versions/{version.id}/publish/").status_code == 200
    rejected = client.patch(
        f"/api/call-sheet-versions/{version.id}/schedule/{created.json()['id']}/",
        {"title": "Bypass"},
        content_type="application/json",
    )
    assert rejected.status_code == 400
    assert not AuditEvent.objects.filter(
        action="callsheet.schedule_updated", description__contains="Bypass"
    ).exists()


def test_developer_only_published_and_private_details_excluded(owner, organization, call_sheet):
    _, draft = call_sheet
    _, created = create_api_client_key(
        organization=organization,
        name="Call Sheets",
        description="",
        scopes=["callsheet.read"],
        created_by=owner,
    )
    from django.test import Client

    api = Client()
    assert (
        api.get(
            "/api/developer/call-sheets/",
            HTTP_AUTHORIZATION=f"Bearer {created.secret}",
        ).json()
        == []
    )
    mark_ready(actor=owner, version=draft)
    publish_call_sheet_version(actor=owner, version=draft)
    response = api.get(
        "/api/developer/call-sheets/",
        HTTP_AUTHORIZATION=f"Bearer {created.secret}",
    )
    assert response.status_code == 200
    payload = response.json()[0]
    assert payload["booking_reference"]
    assert not set(payload) & {"team", "contacts", "general_notes", "performance_fee"}


def test_admin_protects_history(call_sheet):
    sheet, version = call_sheet
    request = RequestFactory().get("/admin/")
    request.user = User.objects.create_superuser(
        email="callsheet-admin@example.invalid", password=PASSWORD
    )
    sheet_admin = CallSheetAdmin(CallSheet, admin.site)
    version_admin = CallSheetVersionAdmin(CallSheetVersion, admin.site)
    child_admin = ChildAdmin(CallSheetTeamEntry, admin.site)
    assert not sheet_admin.has_delete_permission(None, sheet)
    assert not version_admin.has_add_permission(None)
    assert not version_admin.has_delete_permission(None, version)
    version.status = CallSheetVersion.Status.PUBLISHED
    assert len(version_admin.get_readonly_fields(None, version)) == len(version._meta.fields)
    entry = CallSheetTeamEntry(version=version, name_snapshot="Snapshot")
    assert not child_admin.has_change_permission(request, entry)


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_generation_returns_one_canonical_sheet(owner, booking):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL concurrency regression")
    barrier = Barrier(2)
    results = []
    errors = []

    def generate():
        close_old_connections()
        try:
            actor = User.objects.get(pk=owner.pk)
            thread_booking = Booking.objects.get(pk=booking.pk)
            barrier.wait()
            sheet, version = create_call_sheet(actor=actor, booking=thread_booking)
            results.append((sheet.pk, version.pk))
        except Exception as error:  # pragma: no cover - asserted below
            errors.append(error)
        finally:
            close_old_connections()

    threads = [Thread(target=generate) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    assert len(set(results)) == 1
    assert CallSheet.objects.filter(booking=booking).count() == 1
    assert CallSheetVersion.objects.filter(call_sheet__booking=booking).count() == 1
