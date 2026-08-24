import uuid
from datetime import date
from decimal import Decimal

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError

from artists.models import Artist
from audit.models import AuditEvent
from bookings.admin import BookingAdmin, BookingStatusHistoryAdmin
from bookings.models import Booking, BookingStatusHistory
from bookings.services import (
    assign_contact,
    assign_team_member,
    create_booking,
    transition_booking,
    update_booking,
)
from contacts.models import Contact
from organizations.models import Membership, Organization
from promoters.models import Promoter
from users.models import User
from venues.models import Venue
from white_label.services import create_api_client_key

pytestmark = pytest.mark.django_db
PASSWORD = "Test-only-booking-credential-123"


@pytest.fixture
def org():
    return Organization.objects.create(name="Booking Org", slug="booking-org")


@pytest.fixture
def other_org():
    return Organization.objects.create(name="Other Booking Org", slug="other-booking-org")


def user_with_role(org, role, email):
    user = User.objects.create_user(email=email, password=PASSWORD)
    Membership.objects.create(user=user, organization=org, role=role)
    return user


@pytest.fixture
def owner(org):
    return user_with_role(org, Membership.Role.OWNER, "booking-owner@example.invalid")


@pytest.fixture
def manager(org):
    return user_with_role(org, Membership.Role.MANAGER, "booking-manager@example.invalid")


@pytest.fixture
def member(org):
    return user_with_role(org, Membership.Role.MEMBER, "booking-member@example.invalid")


@pytest.fixture
def artist(org):
    return Artist.objects.create(organization=org, stage_name="Signal North", slug="signal-north")


@pytest.fixture
def promoter(org):
    return Promoter.objects.create(organization=org, name="North Live", slug="north-live")


@pytest.fixture
def venue(org):
    return Venue.objects.create(
        organization=org,
        name="Signal Hall",
        slug="signal-hall",
        city="Cape Town",
        country="South Africa",
    )


@pytest.fixture
def booking(owner, org, artist, promoter, venue):
    return create_booking(
        actor=owner,
        organization=org,
        data={
            "title": "Signal North at Signal Hall",
            "artist": artist,
            "promoter": promoter,
            "venue": venue,
            "event_date": date(2026, 10, 10),
            "performance_fee": Decimal("12000.00"),
        },
    )


def test_booking_uuid_reference_snapshots_and_audit(booking):
    assert isinstance(booking.id, uuid.UUID)
    assert booking.reference.startswith("EV-")
    assert booking.promoter_name_snapshot == "North Live"
    assert (booking.venue_name_snapshot, booking.city_snapshot) == ("Signal Hall", "Cape Town")
    assert AuditEvent.objects.filter(action="booking.created", resource_id=str(booking.id)).exists()


def test_cross_organization_relations_are_rejected(owner, org, other_org, artist):
    other_venue = Venue.objects.create(
        organization=other_org, name="Other", slug="other", city="", country=""
    )
    with pytest.raises(ValidationError):
        create_booking(
            actor=owner,
            organization=org,
            data={
                "title": "Invalid",
                "artist": artist,
                "venue": other_venue,
                "event_date": date.today(),
            },
        )


def test_master_changes_do_not_rewrite_snapshot_but_explicit_change_does(
    owner, booking, venue, org
):
    venue.name = "Renamed Master Venue"
    venue.save()
    booking.refresh_from_db()
    assert booking.venue_name_snapshot == "Signal Hall"
    replacement = Venue.objects.create(
        organization=org, name="New Venue", slug="new-venue", city="Durban", country="South Africa"
    )
    update_booking(actor=owner, booking=booking, data={"venue": replacement})
    assert booking.venue_name_snapshot == "New Venue"
    assert booking.city_snapshot == "Durban"


def test_status_transitions_are_explicit_audited_and_append_only(owner, booking):
    transitioned = transition_booking(
        actor=owner, booking=booking, to_status=Booking.Status.HOLD, reason="Date requested"
    )
    history = BookingStatusHistory.objects.get(booking=booking)
    assert transitioned.status == Booking.Status.HOLD
    assert (history.from_status, history.to_status, history.reason) == (
        Booking.Status.ENQUIRY,
        Booking.Status.HOLD,
        "Date requested",
    )
    with pytest.raises(ValidationError):
        transition_booking(actor=owner, booking=transitioned, to_status=Booking.Status.COMPLETED)
    history.reason = "Changed"
    with pytest.raises(ValidationError):
        history.save()
    with pytest.raises(ValidationError):
        history.delete()


def test_manager_operational_access_excludes_commercial_fields(client, manager, org, artist):
    client.force_login(manager)
    created = client.post(
        "/api/bookings/",
        {
            "organization_id": str(org.id),
            "title": "Manager booking",
            "artist_id": str(artist.id),
            "event_date": "2026-11-01",
        },
        content_type="application/json",
    )
    assert created.status_code == 201
    assert "performance_fee" not in created.json()
    assert (
        client.patch(
            f"/api/bookings/{created.json()['id']}/",
            {"performance_fee": "100.00"},
            content_type="application/json",
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/bookings/",
            {
                "organization_id": str(org.id),
                "title": "Currency bypass",
                "artist_id": str(artist.id),
                "event_date": "2026-11-02",
                "currency": "USD",
            },
            content_type="application/json",
        ).status_code
        == 403
    )


def test_member_reads_safe_booking_data_but_cannot_mutate(client, member, org, booking):
    client.force_login(member)
    listed = client.get("/api/bookings/", {"organization_id": org.id})
    detail = client.get(f"/api/bookings/{booking.id}/")
    assert listed.status_code == detail.status_code == 200
    assert "performance_fee" not in detail.json()
    assert "internal_notes" in detail.json()
    assert (
        client.patch(
            f"/api/bookings/{booking.id}/", {"title": "Denied"}, content_type="application/json"
        ).status_code
        == 403
    )


def test_generic_update_rejects_status(client, owner, booking):
    client.force_login(owner)
    response = client.patch(
        f"/api/bookings/{booking.id}/",
        {"status": Booking.Status.CONFIRMED},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_cross_org_and_staff_only_access_is_hidden(client, booking, other_org):
    outsider = user_with_role(other_org, Membership.Role.OWNER, "outsider@example.invalid")
    client.force_login(outsider)
    assert client.get(f"/api/bookings/{booking.id}/").status_code == 404
    staff = User.objects.create_user(
        email="staff@example.invalid", password=PASSWORD, is_staff=True
    )
    client.force_login(staff)
    assert client.get(f"/api/bookings/{booking.id}/").status_code == 404


def test_team_and_contact_assignments_are_scoped_snapshotted_and_audited(
    owner, org, other_org, booking
):
    membership = Membership.objects.get(user=owner, organization=org)
    team = assign_team_member(
        actor=owner,
        booking=booking,
        membership=membership,
        data={"responsibility": "manager", "is_primary": True},
    )
    contact = Contact.objects.create(
        organization=org,
        first_name="Casey",
        last_name="Jones",
        email="casey@example.invalid",
    )
    assigned = assign_contact(
        actor=owner,
        booking=booking,
        contact=contact,
        data={"responsibility": "promoter", "is_primary": True},
    )
    contact.first_name = "Changed"
    contact.save()
    assigned.refresh_from_db()
    assert team.is_primary
    assert assigned.snapshot_name == "Casey Jones"
    assert set(AuditEvent.objects.values_list("action", flat=True)) >= {
        "booking.team_assigned",
        "booking.contact_added",
    }
    other_membership = Membership.objects.create(
        user=User.objects.create_user(email="other-member@example.invalid", password=PASSWORD),
        organization=other_org,
        role=Membership.Role.MEMBER,
    )
    with pytest.raises(ValidationError):
        assign_team_member(
            actor=owner,
            booking=booking,
            membership=other_membership,
            data={"responsibility": "general"},
        )
    inactive = Membership.objects.create(
        user=User.objects.create_user(email="inactive-booking@example.invalid", password=PASSWORD),
        organization=org,
        role=Membership.Role.MEMBER,
        is_active=False,
    )
    with pytest.raises(ValidationError):
        assign_team_member(
            actor=owner,
            booking=booking,
            membership=inactive,
            data={"responsibility": "general"},
        )


def test_developer_api_is_scoped_and_excludes_sensitive_data(owner, org, booking):
    _, created_key = create_api_client_key(
        organization=org,
        name="Booking integration",
        description="",
        scopes=["booking.read"],
        created_by=owner,
    )
    response = (
        pytest.importorskip("rest_framework.test")
        .APIClient()
        .get(
            "/api/developer/bookings/",
            HTTP_AUTHORIZATION=f"Bearer {created_key.secret}",
        )
    )
    assert response.status_code == 200
    payload = response.json()[0]
    assert payload["id"] == str(booking.id)
    for field in ("performance_fee", "deposit_amount", "internal_notes", "contact_assignments"):
        assert field not in payload
    _, denied_key = create_api_client_key(
        organization=org,
        name="Denied integration",
        description="",
        scopes=["organization.read"],
        created_by=owner,
    )
    denied = (
        pytest.importorskip("rest_framework.test")
        .APIClient()
        .get(
            "/api/developer/bookings/",
            HTTP_AUTHORIZATION=f"Bearer {denied_key.secret}",
        )
    )
    assert denied.status_code == 403


def test_platform_superuser_can_read_cross_organization(client, booking):
    platform_user = User.objects.create_superuser(
        email="booking-platform@example.invalid", password=PASSWORD
    )
    client.force_login(platform_user)
    response = client.get(f"/api/platform/bookings/{booking.id}/")
    assert response.status_code == 200
    assert response.json()["performance_fee"] == "12000.00"


def test_booking_admin_prevents_deletion_and_history_is_read_only(booking):
    booking_admin = BookingAdmin(Booking, admin.site)
    history_admin = BookingStatusHistoryAdmin(BookingStatusHistory, admin.site)
    assert not booking_admin.has_delete_permission(None, booking)
    assert not history_admin.has_add_permission(None)
    assert not history_admin.has_change_permission(None)
    assert not history_admin.has_delete_permission(None)
