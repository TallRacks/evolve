from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from artists.models import Artist, ArtistPortalLink
from bookings.models import Booking
from calendar_app.selectors import get_calendar_items
from callsheets.models import CallSheet, CallSheetVersion
from callsheets.services import import_travel_from_itinerary
from documents.models import Document, DocumentLink
from organizations.models import Membership, Organization
from travel.models import (
    AccommodationRoomAssignment,
    AccommodationStay,
    ItineraryTraveller,
    TravelItinerary,
    TravelSegment,
    TravelSegmentTraveller,
)
from travel.services import create_itinerary, transition_itinerary
from users.models import User
from white_label.services import create_api_client_key

pytestmark = pytest.mark.django_db
PASSWORD = "Travel-test-only-credential-123"


@pytest.fixture
def foundation():
    organization = Organization.objects.create(name="Travel Test", slug="travel-test")
    other = Organization.objects.create(name="Other Travel", slug="other-travel")
    owner = User.objects.create_user(email="travel-owner@example.invalid", password=PASSWORD)
    manager = User.objects.create_user(email="travel-manager@example.invalid", password=PASSWORD)
    member = User.objects.create_user(email="travel-member@example.invalid", password=PASSWORD)
    artist_user = User.objects.create_user(email="travel-artist@example.invalid", password=PASSWORD)
    Membership.objects.create(organization=organization, user=owner, role=Membership.Role.OWNER)
    manager_membership = Membership.objects.create(
        organization=organization, user=manager, role=Membership.Role.MANAGER
    )
    Membership.objects.create(organization=organization, user=member, role=Membership.Role.MEMBER)
    Membership.objects.create(
        organization=organization, user=artist_user, role=Membership.Role.ARTIST
    )
    artist = Artist.objects.create(
        organization=organization, stage_name="Travel Artist", slug="travel-artist"
    )
    other_artist = Artist.objects.create(
        organization=other, stage_name="Private Artist", slug="private-artist"
    )
    ArtistPortalLink.objects.create(artist=artist, user=artist_user)
    booking = Booking.objects.create(
        organization=organization,
        artist=artist,
        title="Travel Show",
        event_date=timezone.localdate() + timedelta(days=5),
        created_by=owner,
    )
    return (
        organization,
        other,
        owner,
        manager,
        member,
        artist_user,
        manager_membership,
        artist,
        other_artist,
        booking,
    )


def itinerary_data(artist, booking=None):
    now = timezone.now() + timedelta(days=1)
    return {
        "artist": artist,
        "booking": booking,
        "title": "Tour itinerary",
        "starts_at": now,
        "ends_at": now + timedelta(days=3),
        "timezone": "Africa/Johannesburg",
    }


def test_itinerary_integrity_lifecycle_permissions_and_audit(foundation):
    organization, _, owner, manager, member, _, _, artist, other_artist, booking = foundation
    item = create_itinerary(
        actor=manager, organization=organization, data=itinerary_data(artist, booking)
    )
    assert item.id and item.status == TravelItinerary.Status.DRAFT
    transition_itinerary(item, actor=manager, to_status=TravelItinerary.Status.CONFIRMED)
    item.refresh_from_db()
    assert item.status == TravelItinerary.Status.CONFIRMED
    with pytest.raises(ValidationError):
        transition_itinerary(item, actor=manager, to_status=TravelItinerary.Status.ARCHIVED)
    with pytest.raises(PermissionDenied):
        create_itinerary(actor=member, organization=organization, data=itinerary_data(artist))
    invalid = TravelItinerary(organization=organization, artist=other_artist, title="Cross org")
    with pytest.raises(ValidationError):
        invalid.save()
    assert organization.audit_events.filter(action="travel.itinerary_status_changed").exists()


def test_traveller_segment_room_scope_and_sensitive_boundaries(foundation):
    organization, other, owner, _, _, _, manager_membership, artist, other_artist, booking = (
        foundation
    )
    item = TravelItinerary.objects.create(
        organization=organization, artist=artist, booking=booking, title="Scope", created_by=owner
    )
    artist_row = ItineraryTraveller.objects.create(
        itinerary=item, artist=artist, traveller_type="artist", display_name="Artist"
    )
    team = ItineraryTraveller.objects.create(
        itinerary=item, membership=manager_membership, traveller_type="team", display_name="Manager"
    )
    external = ItineraryTraveller.objects.create(
        itinerary=item, traveller_type="guest", display_name="Guest"
    )
    cross = ItineraryTraveller(itinerary=item, artist=other_artist, traveller_type="artist")
    with pytest.raises(ValidationError):
        cross.save()
    now = timezone.now() + timedelta(days=1)
    segment = TravelSegment.objects.create(
        itinerary=item,
        segment_type="flight",
        sequence=1,
        departure_location="Johannesburg",
        arrival_location="London",
        departure_at=now,
        arrival_at=now + timedelta(hours=10),
        departure_timezone="Africa/Johannesburg",
        arrival_timezone="Europe/London",
        departure_airport_code="JNB",
        arrival_airport_code="LHR",
        confirmation_reference="PRIVATE-REF",
    )
    TravelSegmentTraveller.objects.create(segment=segment, traveller=team, seat="12A")
    stay = AccommodationStay.objects.create(
        itinerary=item,
        property_name="Hotel",
        city="London",
        country="GB",
        timezone="Europe/London",
        check_in_at=now + timedelta(hours=12),
        check_out_at=now + timedelta(days=2),
        confirmation_reference="HOTEL-PRIVATE",
    )
    AccommodationRoomAssignment.objects.create(stay=stay, traveller=external, room_label="Room A")
    other_item = TravelItinerary.objects.create(
        organization=other, artist=other_artist, title="Other", created_by=owner
    )
    other_traveller = ItineraryTraveller.objects.create(
        itinerary=other_item, traveller_type="guest", display_name="Other"
    )
    with pytest.raises(ValidationError):
        TravelSegmentTraveller.objects.create(segment=segment, traveller=other_traveller)
    with pytest.raises(ValidationError):
        AccommodationRoomAssignment.objects.create(stay=stay, traveller=other_traveller)
    assert artist_row.id


def test_workspace_api_artist_privacy_platform_and_search(client, foundation):
    organization, _, owner, manager, member, artist_user, _, artist, _, booking = foundation
    item = TravelItinerary.objects.create(
        organization=organization,
        artist=artist,
        booking=booking,
        title="Needle Journey",
        created_by=owner,
    )
    now = timezone.now() + timedelta(days=1)
    TravelSegment.objects.create(
        itinerary=item,
        segment_type="ground",
        sequence=1,
        provider="Needle Transport",
        confirmation_reference="SECRET-CONFIRM",
        departure_location="Airport",
        arrival_location="Hotel",
        departure_at=now,
        departure_timezone="Africa/Johannesburg",
        arrival_timezone="Africa/Johannesburg",
        driver_phone="+27000000000",
    )
    for user, expected in ((manager, 200), (member, 200)):
        client.force_login(user)
        assert (
            client.get(f"/api/travel/itineraries/?organization_id={organization.id}").status_code
            == expected
        )
    client.force_login(manager)
    base_url = f"/api/travel/itineraries/?organization_id={organization.id}"
    assert client.get(f"{base_url}&start=not-a-date").status_code == 400
    assert client.get(f"{base_url}&end=not-a-date").status_code == 400
    assert client.get(f"{base_url}&offset=not-an-integer").status_code == 400
    client.force_login(member)
    member_detail = str(client.get(f"/api/travel/itineraries/{item.id}/").json())
    assert "SECRET-CONFIRM" not in member_detail and "+27000000000" not in member_detail
    client.force_login(manager)
    assert "SECRET-CONFIRM" in str(client.get(f"/api/travel/itineraries/{item.id}/").json())
    client.force_login(artist_user)
    response = client.get("/api/artist/travel/")
    assert response.status_code == 200
    payload = str(response.json())
    assert "SECRET-CONFIRM" not in payload and "+27000000000" not in payload
    assert (
        client.get(f"/api/travel/itineraries/?organization_id={organization.id}").status_code == 403
    )
    client.force_login(member)
    search = client.get(f"/api/search/?q=Needle&organization_id={organization.id}").json()
    assert "Needle Journey" in str(search)
    assert "SECRET-CONFIRM" not in str(search)
    staff = User.objects.create_user(
        email="travel-staff@example.invalid", password=PASSWORD, is_staff=True
    )
    client.force_login(staff)
    assert client.get("/api/platform/travel/").status_code == 403
    superuser = User.objects.create_superuser(
        email="travel-super@example.invalid", password=PASSWORD
    )
    client.force_login(superuser)
    assert client.get("/api/platform/travel/").status_code == 200


def test_calendar_document_and_callsheet_snapshot_import(foundation):
    organization, _, owner, _, _, _, _, artist, _, booking = foundation
    now = timezone.now() + timedelta(days=1)
    item = TravelItinerary.objects.create(
        organization=organization,
        artist=artist,
        booking=booking,
        title="Integrated",
        created_by=owner,
    )
    segment = TravelSegment.objects.create(
        itinerary=item,
        segment_type="rail",
        sequence=1,
        provider="Rail",
        departure_location="A",
        arrival_location="B",
        departure_at=now,
        arrival_at=now + timedelta(hours=2),
        departure_timezone="Europe/London",
        arrival_timezone="Europe/London",
    )
    AccommodationStay.objects.create(
        itinerary=item,
        property_name="Hotel",
        city="B",
        country="GB",
        timezone="Europe/London",
        check_in_at=now + timedelta(hours=3),
        check_out_at=now + timedelta(days=1),
        sequence=1,
    )
    items = get_calendar_items(
        owner, organization, now - timedelta(hours=1), now + timedelta(days=2)
    )
    assert {x["source_type"] for x in items} >= {"travel", "accommodation"}
    document = Document.objects.create(
        organization=organization,
        title="Travel confirmation",
        document_type="travel",
        external_url="https://example.invalid/travel",
        uploaded_by=owner,
    )
    DocumentLink.objects.create(document=document, travel_itinerary=item)
    DocumentLink.objects.create(document=document, travel_segment=segment)
    call_sheet = CallSheet.objects.create(
        organization=organization, booking=booking, created_by=owner
    )
    version = CallSheetVersion.objects.create(
        call_sheet=call_sheet,
        version_number=1,
        title="Draft",
        event_name="Show",
        artist_name=artist.stage_name,
        event_date=booking.event_date,
        timezone="Africa/Johannesburg",
        status="draft",
        created_by=owner,
    )
    import_travel_from_itinerary(actor=owner, version=version)
    assert version.travel_items.count() == 1 and version.accommodation_items.count() == 1
    CallSheetVersion.objects.filter(pk=version.pk).update(status="published")
    version.refresh_from_db()
    with pytest.raises(ValidationError):
        import_travel_from_itinerary(actor=owner, version=version)


def test_developer_scope_and_safe_representation(client, foundation):
    organization, _, owner, _, _, _, _, artist, _, booking = foundation
    TravelItinerary.objects.create(
        organization=organization,
        artist=artist,
        booking=booking,
        title="Developer Travel",
        notes="private",
        created_by=owner,
    )
    _, created = create_api_client_key(
        organization=organization,
        name="Travel reader",
        description="",
        scopes=["travel.read"],
        created_by=owner,
    )
    response = client.get(
        "/api/developer/travel/itineraries/", HTTP_AUTHORIZATION=f"Bearer {created.secret}"
    )
    assert response.status_code == 200
    payload = str(response.json())
    assert (
        "Developer Travel" in payload
        and "private" not in payload
        and "confirmation_reference" not in payload
    )
    _, denied = create_api_client_key(
        organization=organization,
        name="No travel",
        description="",
        scopes=["artist.read"],
        created_by=owner,
    )
    assert (
        client.get(
            "/api/developer/travel/itineraries/", HTTP_AUTHORIZATION=f"Bearer {denied.secret}"
        ).status_code
        == 403
    )
