from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from artists.models import Artist, ArtistPortalLink
from bookings.models import Booking
from calendar_app.selectors import get_calendar_items
from callsheets.models import CallSheet, CallSheetVersion
from callsheets.services import import_production_from_advance
from contacts.models import Contact
from documents.models import Document, DocumentLink
from organizations.models import Membership, Organization
from production.models import (
    AdvanceChecklistItem,
    AdvanceRequirement,
    ProductionAdvance,
    ProductionContactAssignment,
    ProductionScheduleItem,
)
from production.services import (
    REQUIREMENT_TRANSITIONS,
    create_advance,
    create_child,
    set_checklist_completion,
    transition_advance,
    transition_child,
)
from promoters.models import Promoter
from users.models import User
from venues.models import Venue
from white_label.services import create_api_client_key

pytestmark = pytest.mark.django_db
PASSWORD = "Production-test-only-credential-123"


@pytest.fixture
def foundation():
    organization = Organization.objects.create(name="Production Test", slug="production-test")
    other = Organization.objects.create(name="Other Production", slug="other-production")
    owner = User.objects.create_user(email="production-owner@example.invalid", password=PASSWORD)
    manager = User.objects.create_user(
        email="production-manager@example.invalid", password=PASSWORD
    )
    member = User.objects.create_user(email="production-member@example.invalid", password=PASSWORD)
    artist_user = User.objects.create_user(
        email="production-artist@example.invalid", password=PASSWORD
    )
    Membership.objects.create(organization=organization, user=owner, role="owner")
    manager_membership = Membership.objects.create(
        organization=organization, user=manager, role="manager"
    )
    Membership.objects.create(organization=organization, user=member, role="member")
    Membership.objects.create(organization=organization, user=artist_user, role="artist")
    artist = Artist.objects.create(
        organization=organization, stage_name="Production Artist", slug="production-artist"
    )
    other_artist = Artist.objects.create(
        organization=other, stage_name="Other Artist", slug="other-artist"
    )
    ArtistPortalLink.objects.create(artist=artist, user=artist_user)
    venue = Venue.objects.create(
        organization=organization,
        name="Production Venue",
        slug="production-venue",
        timezone="Africa/Johannesburg",
    )
    promoter = Promoter.objects.create(
        organization=organization, name="Production Promoter", slug="production-promoter"
    )
    booking = Booking.objects.create(
        organization=organization,
        artist=artist,
        venue=venue,
        promoter=promoter,
        title="Production Show",
        event_date=timezone.localdate() + timedelta(days=5),
        created_by=owner,
    )
    return {
        "organization": organization,
        "other": other,
        "owner": owner,
        "manager": manager,
        "member": member,
        "artist_user": artist_user,
        "manager_membership": manager_membership,
        "artist": artist,
        "other_artist": other_artist,
        "venue": venue,
        "promoter": promoter,
        "booking": booking,
    }


def make_advance(data):
    return create_advance(
        actor=data["manager"],
        organization=data["organization"],
        data={"booking": data["booking"], "production_title": "Show Advance"},
    )


def test_advance_integrity_duplicate_lifecycle_permissions_and_audit(foundation):
    advance = make_advance(foundation)
    assert advance.id and advance.artist == foundation["artist"]
    assert advance.venue == foundation["venue"] and advance.promoter == foundation["promoter"]
    with pytest.raises(ValidationError):
        ProductionAdvance.objects.create(
            organization=foundation["other"],
            booking=foundation["booking"],
            artist=foundation["artist"],
            production_title="Cross organization",
        )
    with pytest.raises(ValidationError):
        ProductionAdvance.objects.create(
            organization=foundation["organization"],
            booking=foundation["booking"],
            artist=foundation["artist"],
            production_title="Duplicate",
            created_by=foundation["manager"],
        )
    transition_advance(advance, actor=foundation["manager"], to_status="in_progress")
    advance.refresh_from_db()
    assert advance.status == "in_progress"
    with pytest.raises(ValidationError):
        transition_advance(advance, actor=foundation["manager"], to_status="archived")
    with pytest.raises(PermissionDenied):
        create_advance(
            actor=foundation["member"],
            organization=foundation["organization"],
            data={"booking": foundation["booking"]},
        )
    assert (
        foundation["organization"]
        .audit_events.filter(action="production.advance_status_changed")
        .exists()
    )


def test_requirements_contacts_schedule_checklist_and_constraints(foundation):
    advance = make_advance(foundation)
    requirement = create_child(
        AdvanceRequirement,
        advance,
        actor=foundation["manager"],
        data={
            "category": "technical",
            "title": "Four wireless microphones",
            "priority": "critical",
            "assigned_membership": foundation["manager_membership"],
        },
        permission="production.requirements.manage",
        action="production.requirement_created",
    )
    second_requirement = create_child(
        AdvanceRequirement,
        advance,
        actor=foundation["manager"],
        data={"category": "hospitality", "title": "Secure dressing room"},
        permission="production.requirements.manage",
        action="production.requirement_created",
    )
    assert (requirement.sequence, second_requirement.sequence) == (1, 2)
    transition_child(
        requirement,
        actor=foundation["manager"],
        to_status="blocked",
        permission="production.requirements.manage",
        transitions=REQUIREMENT_TRANSITIONS,
        action="production.requirement_status_changed",
    )
    contact = Contact.objects.create(
        organization=foundation["organization"],
        first_name="Venue",
        last_name="Manager",
        email="venue@example.invalid",
    )
    ProductionContactAssignment.objects.create(
        advance=advance, contact=contact, role="venue", is_primary=True
    )
    with pytest.raises(ValidationError):
        ProductionContactAssignment.objects.create(
            advance=advance, contact=contact, role="venue", is_primary=True
        )
    other_contact = Contact.objects.create(
        organization=foundation["other"], first_name="Other", last_name="Contact"
    )
    with pytest.raises(ValidationError):
        ProductionContactAssignment.objects.create(
            advance=advance, contact=other_contact, role="other"
        )
    now = timezone.now() + timedelta(days=1)
    ProductionScheduleItem.objects.create(
        advance=advance,
        title="Soundcheck",
        item_type="soundcheck",
        starts_at=now,
        ends_at=now + timedelta(hours=1),
        timezone="Africa/Johannesburg",
    )
    with pytest.raises(ValidationError):
        ProductionScheduleItem.objects.create(
            advance=advance,
            title="Invalid",
            item_type="doors",
            starts_at=now,
            ends_at=now - timedelta(hours=1),
            timezone="Africa/Johannesburg",
            sequence=2,
        )
    checklist = AdvanceChecklistItem.objects.create(
        advance=advance,
        title="Send stage plot",
        assigned_membership=foundation["manager_membership"],
    )
    set_checklist_completion(checklist, actor=foundation["manager"], completed=True)
    checklist.refresh_from_db()
    assert checklist.is_completed and checklist.completed_by == foundation["manager"]
    set_checklist_completion(checklist, actor=foundation["manager"], completed=False)
    checklist.refresh_from_db()
    assert not checklist.is_completed and checklist.completed_at is None


def test_workspace_artist_platform_search_and_developer_privacy(client, foundation):
    advance = make_advance(foundation)
    advance.production_notes = "PRIVATE MANAGEMENT"
    advance.security_notes = "PRIVATE SECURITY"
    advance.save()
    AdvanceRequirement.objects.create(
        advance=advance,
        category="technical",
        title="Artist-safe item",
        description="PRIVATE REQUIREMENT",
        source="artist",
        created_by=foundation["manager"],
    )
    contact = Contact.objects.create(
        organization=foundation["organization"],
        first_name="Private",
        last_name="Contact",
        email="private-contact@example.invalid",
        phone="+27000000000",
    )
    ProductionContactAssignment.objects.create(
        advance=advance, contact=contact, role="production_manager", is_primary=True
    )
    for user, expected in (
        (foundation["manager"], 200),
        (foundation["member"], 200),
    ):
        client.force_login(user)
        assert (
            client.get(
                f"/api/production/advances/?organization_id={foundation['organization'].id}"
            ).status_code
            == expected
        )
    client.force_login(foundation["artist_user"])
    response = client.get("/api/artist/production/")
    payload = str(response.json())
    assert response.status_code == 200 and "Show Advance" in payload
    assert "PRIVATE MANAGEMENT" not in payload and "PRIVATE SECURITY" not in payload
    assert "private-contact@example.invalid" not in payload and "+27000000000" not in payload
    assert client.get(f"/api/production/advances/{advance.id}/").status_code == 403
    client.force_login(foundation["member"])
    search = str(
        client.get(f"/api/search/?q=Show&organization_id={foundation['organization'].id}").json()
    )
    assert "Show Advance" in search and "PRIVATE MANAGEMENT" not in search
    staff = User.objects.create_user(
        email="production-staff@example.invalid", password=PASSWORD, is_staff=True
    )
    client.force_login(staff)
    assert client.get("/api/platform/production/").status_code == 403
    assert client.get("/admin/production/productionadvance/").status_code == 403
    superuser = User.objects.create_superuser(
        email="production-super@example.invalid", password=PASSWORD
    )
    client.force_login(superuser)
    assert client.get("/api/platform/production/").status_code == 200
    assert client.get("/admin/production/productionadvance/").status_code == 200
    _, key = create_api_client_key(
        organization=foundation["organization"],
        name="Production reader",
        description="",
        scopes=["production.read"],
        created_by=foundation["owner"],
    )
    response = client.get(
        "/api/developer/production/advances/",
        HTTP_AUTHORIZATION=f"Bearer {key.secret}",
    )
    developer = str(response.json())
    assert response.status_code == 200 and "Show Advance" in developer
    assert "PRIVATE" not in developer and "private-contact" not in developer


def test_calendar_documents_and_callsheet_snapshot_immutability(foundation):
    advance = make_advance(foundation)
    now = timezone.now() + timedelta(days=1)
    advance.advance_due_at = now
    advance.save()
    ProductionScheduleItem.objects.create(
        advance=advance,
        title="Soundcheck",
        item_type="soundcheck",
        starts_at=now + timedelta(hours=1),
        timezone="Africa/Johannesburg",
    )
    ProductionScheduleItem.objects.create(
        advance=advance,
        title="Show",
        item_type="show",
        starts_at=now + timedelta(hours=3),
        timezone="Africa/Johannesburg",
        sequence=2,
    )
    contact = Contact.objects.create(
        organization=foundation["organization"], first_name="Show", last_name="Contact"
    )
    ProductionContactAssignment.objects.create(
        advance=advance, contact=contact, role="production_manager", is_primary=True
    )
    AdvanceRequirement.objects.create(
        advance=advance,
        category="technical",
        title="Stage plot",
        created_by=foundation["manager"],
    )
    items = get_calendar_items(
        foundation["manager"],
        foundation["organization"],
        now - timedelta(hours=1),
        now + timedelta(days=1),
    )
    production_items = [x for x in items if x["source_type"] == "production"]
    assert len(production_items) == 2
    document = Document.objects.create(
        organization=foundation["organization"],
        title="Stage plot",
        document_type="rider",
        external_url="https://example.invalid/stage-plot",
        uploaded_by=foundation["manager"],
    )
    DocumentLink.objects.create(document=document, production_advance=advance)
    sheet = CallSheet.objects.create(
        organization=foundation["organization"],
        booking=foundation["booking"],
        created_by=foundation["manager"],
    )
    version = CallSheetVersion.objects.create(
        call_sheet=sheet,
        version_number=1,
        title="Draft",
        event_name="Show",
        artist_name=foundation["artist"].stage_name,
        event_date=foundation["booking"].event_date,
        timezone="Africa/Johannesburg",
        status="draft",
        created_by=foundation["manager"],
    )
    import_production_from_advance(actor=foundation["manager"], version=version)
    assert version.schedule_items.count() == 2
    snapshot_title = version.schedule_items.first().title
    CallSheetVersion.objects.filter(pk=version.pk).update(status="published")
    version.refresh_from_db()
    ProductionScheduleItem.objects.filter(title="Soundcheck").update(title="Changed")
    assert version.schedule_items.first().title == snapshot_title
    with pytest.raises(ValidationError):
        import_production_from_advance(actor=foundation["manager"], version=version)
