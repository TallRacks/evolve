from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError

from artists.models import Artist, ArtistPortalLink
from audit.models import AuditEvent
from bookings.models import Booking
from calendar_app.admin import CalendarEventAdmin
from calendar_app.models import CalendarEvent
from calendar_app.selectors import get_calendar_items
from calendar_app.services import create_event, transition_event
from documents.admin import DocumentAdmin
from documents.api.serializers import PlatformDocumentSummarySerializer, PortalDocumentSerializer
from documents.models import Document, DocumentLink
from documents.selectors import developer_documents, documents_for_user, portal_documents
from documents.services import archive_document, create_document, create_version, link_document
from music.models import Release
from organizations.models import Membership, Organization
from users.models import User

pytestmark = pytest.mark.django_db
PASSWORD = "Test-only-calendar-document-credential-123"


def member(org, role, email):
    user = User.objects.create_user(email=email, password=PASSWORD)
    return user, Membership.objects.create(user=user, organization=org, role=role)


@pytest.fixture
def setup():
    org = Organization.objects.create(name="Schedule Org", slug="schedule-org")
    other = Organization.objects.create(name="Other Schedule", slug="other-schedule")
    owner = member(org, Membership.Role.OWNER, "schedule-owner@example.invalid")
    artist_user = member(org, Membership.Role.ARTIST, "schedule-artist@example.invalid")
    artist = Artist.objects.create(
        organization=org, stage_name="Schedule Artist", slug="schedule-artist"
    )
    ArtistPortalLink.objects.create(artist=artist, user=artist_user[0])
    return org, other, owner, artist_user, artist


def window():
    tz = ZoneInfo("Africa/Johannesburg")
    return datetime(2027, 1, 1, tzinfo=tz), datetime(2027, 1, 31, 23, 59, tzinfo=tz)


def test_calendar_projection_sources_are_not_persisted(setup):
    org, _, owner, _, artist = setup
    booking = Booking.objects.create(
        organization=org,
        artist=artist,
        title="Live show",
        event_date=date(2027, 1, 12),
        created_by=owner[0],
    )
    Release.objects.create(
        organization=org,
        primary_artist=artist,
        title="Single",
        slug="single",
        release_type="single",
        planned_release_date=date(2027, 1, 20),
    )
    items = get_calendar_items(owner[0], org, *window())
    assert {item["source_type"] for item in items} == {"booking", "release"}
    assert items[0]["starts_at"].endswith("+02:00")
    assert CalendarEvent.objects.count() == 0
    assert booking.performance_fee is None


def test_calendar_range_filter_visibility_and_isolation(setup):
    org, other, owner, _, artist = setup
    public = create_event(
        actor=owner[0],
        organization=org,
        title="Team",
        event_type="meeting",
        starts_at=window()[0],
        timezone="Africa/Johannesburg",
    )
    private = create_event(
        actor=owner[0],
        organization=org,
        title="Private",
        event_type="admin",
        starts_at=window()[0],
        timezone="Africa/Johannesburg",
        visibility="private",
    )
    outsider = member(org, Membership.Role.MEMBER, "calendar-member@example.invalid")[0]
    titles = {item["title"] for item in get_calendar_items(outsider, org, *window())}
    assert titles == {public.title}
    assert private.title not in titles
    with pytest.raises(ValueError):
        get_calendar_items(owner[0], org, window()[0], window()[0] + timedelta(days=367))
    assert not get_calendar_items(owner[0], other, *window())


def test_artist_portal_calendar_only_explicit_artist_items(setup):
    org, _, owner, artist_user, artist = setup
    create_event(
        actor=owner[0],
        organization=org,
        title="Artist rehearsal",
        event_type="rehearsal",
        starts_at=window()[0],
        timezone="Africa/Johannesburg",
        visibility="artist_team",
        artist=artist,
    )
    create_event(
        actor=owner[0],
        organization=org,
        title="Internal",
        event_type="meeting",
        starts_at=window()[0],
        timezone="Africa/Johannesburg",
    )
    items = get_calendar_items(artist_user[0], org, *window(), portal=True)
    assert {item["title"] for item in items} == {"Artist rehearsal"}


def test_calendar_lifecycle_audit_and_admin(setup):
    org, _, owner, _, _ = setup
    event = create_event(
        actor=owner[0],
        organization=org,
        title="Cancel me",
        event_type="other",
        starts_at=window()[0],
        timezone="Africa/Johannesburg",
    )
    event.status = "cancelled"
    with pytest.raises(ValidationError):
        event.save()
    transition_event(event, "cancelled", actor=owner[0])
    assert AuditEvent.objects.filter(
        action="calendar.event_cancelled", resource_id=str(event.pk)
    ).exists()
    assert not CalendarEventAdmin(CalendarEvent, admin.site).has_delete_permission(None, event)


def test_document_creation_archive_version_and_audit(setup):
    org, _, owner, _, _ = setup
    document = create_document(
        actor=owner[0],
        organization=org,
        title="Agreement",
        document_type="contract",
        external_url="https://files.example.invalid/agreement.pdf",
        original_filename="agreement.pdf",
    )
    version = create_version(
        document,
        actor=owner[0],
        external_url="https://files.example.invalid/agreement-v2.pdf",
        original_filename="agreement-v2.pdf",
    )
    assert version.parent_document == document and version.version_number == 2
    archive_document(document, actor=owner[0])
    assert document.status == Document.Status.ARCHIVED
    assert AuditEvent.objects.filter(action="document.version_created").exists()
    with pytest.raises(ValidationError):
        document.delete()


def test_document_storage_and_sensitive_type_policy(setup):
    org, _, owner, _, _ = setup
    with pytest.raises(ValidationError):
        create_document(
            actor=owner[0],
            organization=org,
            title="Local",
            document_type="other",
            external_url="file:///etc/passwd",
        )
    assert "identification" not in Document.Type.values
    assert not hasattr(Document, "file")


def test_document_typed_links_and_cross_org_rejection(setup):
    org, other, owner, _, artist = setup
    document = create_document(
        actor=owner[0],
        organization=org,
        title="Press",
        document_type="press",
        external_url="https://files.example.invalid/press.pdf",
    )
    link = link_document(document, actor=owner[0], artist=artist)
    assert link.entity_type == "artist"
    other_artist = Artist.objects.create(organization=other, stage_name="Other", slug="other")
    with pytest.raises(ValidationError):
        link_document(document, actor=owner[0], artist=other_artist)
    with pytest.raises(ValidationError):
        DocumentLink(document=document, artist=artist, booking=Booking()).full_clean()


def test_document_visibility_portal_and_developer_curation(setup):
    org, _, owner, artist_user, artist = setup
    organization_doc = create_document(
        actor=owner[0],
        organization=org,
        title="General",
        document_type="other",
        external_url="https://files.example.invalid/general.pdf",
    )
    restricted = create_document(
        actor=owner[0],
        organization=org,
        title="Restricted",
        document_type="contract",
        external_url="https://files.example.invalid/private.pdf",
        visibility="restricted",
    )
    artist_doc = create_document(
        actor=owner[0],
        organization=org,
        title="Artist press",
        document_type="press",
        external_url="https://files.example.invalid/artist.pdf",
        visibility="artist",
    )
    link_document(artist_doc, actor=owner[0], artist=artist)
    member_user = member(org, Membership.Role.MEMBER, "document-member@example.invalid")[0]
    assert restricted not in documents_for_user(member_user, org)
    assert list(portal_documents(artist_user[0], org)) == [artist_doc]
    assert list(developer_documents(org)) == [organization_doc]
    portal_data = PortalDocumentSerializer(artist_doc).data
    platform_data = PlatformDocumentSummarySerializer(organization_doc).data
    assert "uploader" not in portal_data and "description" not in portal_data
    assert "external_url" not in platform_data


def test_staff_no_bypass_superuser_cross_org_and_admin_delete(setup):
    org, other, owner, _, _ = setup
    document = create_document(
        actor=owner[0],
        organization=org,
        title="Admin",
        document_type="other",
        external_url="https://files.example.invalid/admin.pdf",
    )
    staff = User.objects.create_user(
        email="staff-doc@example.invalid", password=PASSWORD, is_staff=True
    )
    assert not documents_for_user(staff, org).exists()
    root = User.objects.create_superuser(email="root-doc@example.invalid", password=PASSWORD)
    assert document in documents_for_user(root, org)
    assert not DocumentAdmin(Document, admin.site).has_delete_permission(None, document)
