from datetime import date
from types import SimpleNamespace

import pytest

from artists.models import Artist
from bookings.models import Booking
from organizations.models import Organization
from promoters.models import Promoter
from trackers import services
from users.models import User
from venues.models import Venue

pytestmark = pytest.mark.django_db


def test_sheet_import_preserves_existing_partners_and_optional_values(monkeypatch):
    organization = Organization.objects.create(name="Tracker Org", slug="tracker-org")
    actor = User.objects.create_superuser(
        email="tracker-root@example.invalid", password="tracker-test-password"
    )
    artist = Artist.objects.create(
        organization=organization, stage_name="Tracker Artist", slug="tracker-artist"
    )
    promoter = Promoter.objects.create(
        organization=organization, name="Existing Promoter", slug="existing-promoter"
    )
    venue = Venue.objects.create(
        organization=organization, name="Existing Venue", slug="existing-venue"
    )
    booking = Booking.objects.create(
        organization=organization,
        artist=artist,
        promoter=promoter,
        venue=venue,
        title="Existing Show",
        event_date=date(2026, 10, 10),
        promoter_name_snapshot=promoter.name,
        venue_name_snapshot=venue.name,
        performance_type="DJ",
        event_type="Concert",
        created_by=actor,
    )
    tracker = SimpleNamespace(
        organization=organization,
        kind="bookings",
        field_mapping={},
    )
    headers = ["Booking Reference", "Event Name", "Artist", "Event Date", "Promoter", "Venue"]
    row = [booking.reference, booking.title, artist.stage_name, "10 October 2026", "", ""]
    monkeypatch.setattr(services, "_sheet_table", lambda _: (headers, [row]))

    created, updated, skipped, _ = services._import_booking_rows(tracker, actor)

    booking.refresh_from_db()
    assert (created, updated, skipped) == (0, 1, 0)
    assert booking.promoter_id == promoter.id
    assert booking.venue_id == venue.id
    assert booking.performance_type == "DJ"
    assert booking.event_type == "Concert"
