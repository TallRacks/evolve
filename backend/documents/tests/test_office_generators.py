import pytest
from rest_framework.test import APIClient

from artists.models import Artist
from audit.models import AuditEvent
from bookings.models import Booking
from documents.generator_services import generate_booking_office, generate_release_office
from documents.models import DocumentLink, OfficeDocumentContent
from music.models import Release
from organizations.models import Membership, Organization
from users.models import User

pytestmark = pytest.mark.django_db


def setup_org(suffix):
    org = Organization.objects.create(name=f"Generator {suffix}", slug=f"generator-{suffix}")
    user = User.objects.create_user(
        email=f"owner-{suffix}@example.invalid", password="test-password-123"
    )
    Membership.objects.create(user=user, organization=org, role=Membership.Role.OWNER)
    artist = Artist.objects.create(
        organization=org, stage_name=f"Artist {suffix}", slug=f"artist-{suffix}"
    )
    booking = Booking.objects.create(
        organization=org, artist=artist, title="Summer show", event_date="2026-10-20"
    )
    release = Release.objects.create(
        organization=org,
        primary_artist=artist,
        title="New record",
        slug=f"release-{suffix}",
        release_type=Release.Type.SINGLE,
    )
    return user, org, artist, booking, release


def test_booking_generators_are_linked_and_idempotent():
    user, org, artist, booking, _ = setup_org("booking")
    first, reused = generate_booking_office(actor=user, booking=booking, generator="booking-brief")
    second, reused_again = generate_booking_office(
        actor=user, booking=booking, generator="booking-brief"
    )
    assert reused is False and reused_again is True and first.pk == second.pk
    assert DocumentLink.objects.filter(document=first, booking=booking).exists()
    assert DocumentLink.objects.filter(document=first, artist=artist).exists()
    assert (
        first.office_content.content_json["content"][2]["content"][0]["text"] == booking.reference
    )
    assert AuditEvent.objects.filter(
        action="office.booking_brief_created", resource_id=str(first.pk)
    ).exists()


def test_booking_meeting_notes_are_not_idempotent():
    user, _, _, booking, _ = setup_org("meeting")
    first, _ = generate_booking_office(actor=user, booking=booking, generator="meeting-note")
    second, _ = generate_booking_office(actor=user, booking=booking, generator="meeting-note")
    assert first.pk != second.pk


def test_booking_generator_denies_cross_org_and_staff_only():
    user, org, _, booking, _ = setup_org("denial")
    other_org = Organization.objects.create(name="Other", slug="other-generator")
    staff = User.objects.create_user(
        email="staff-generator@example.invalid", password="test-password-123", is_staff=True
    )
    with pytest.raises(PermissionError):
        generate_booking_office(actor=staff, booking=booking, generator="booking-brief")
    other_user = User.objects.create_user(
        email="other-generator@example.invalid", password="test-password-123"
    )
    Membership.objects.create(user=other_user, organization=other_org, role=Membership.Role.OWNER)
    with pytest.raises(PermissionError):
        generate_booking_office(actor=other_user, booking=booking, generator="booking-brief")


def test_release_generators_create_document_sheet_and_checklist():
    user, org, artist, _, release = setup_org("release")
    one_sheet, _ = generate_release_office(
        actor=user, release=release, generator="release-one-sheet"
    )
    metadata, _ = generate_release_office(actor=user, release=release, generator="metadata-sheet")
    credits, _ = generate_release_office(actor=user, release=release, generator="credits-sheet")
    checklist, _ = generate_release_office(
        actor=user, release=release, generator="release-checklist"
    )
    assert one_sheet.office_content.format == OfficeDocumentContent.Format.DOCUMENT
    assert metadata.office_content.format == OfficeDocumentContent.Format.SHEET
    assert metadata.office_content.content_json["columns"][0]["name"] == "Track"
    assert credits.office_content.format == OfficeDocumentContent.Format.SHEET
    assert checklist.office_content.format == OfficeDocumentContent.Format.CHECKLIST
    assert DocumentLink.objects.filter(document=one_sheet, release=release).exists()
    assert DocumentLink.objects.filter(document=one_sheet, artist=artist).exists()
    assert AuditEvent.objects.filter(action="office.metadata_sheet_created").exists()


def test_release_generators_reuse_without_overwriting_manual_content_and_missing_data_is_clear():
    user, _, _, _, release = setup_org("refresh")
    document, _ = generate_release_office(
        actor=user, release=release, generator="release-one-sheet"
    )
    original = document.office_content.content_json
    original["content"][2]["content"][0]["text"] = "Manual edit"
    document.office_content.content_json = original
    document.office_content.save(update_fields=("content_json",))
    same, reused = generate_release_office(
        actor=user, release=release, generator="release-one-sheet"
    )
    assert reused is True and same.pk == document.pk
    assert same.office_content.content_json["content"][2]["content"][0]["text"] == "Manual edit"
    assert "Needs Attention" in str(same.office_content.content_json)


def test_release_api_generators_return_document_and_reuse():
    user, org, _, _, release = setup_org("api")
    client = APIClient()
    client.force_authenticate(user)
    path = f"/api/music/releases/{release.pk}/office/release-one-sheet/"
    response = client.post(path, {}, format="json")
    again = client.post(path, {}, format="json")
    assert response.status_code == 200 and response.json()["reused"] is False
    assert again.status_code == 200 and again.json()["reused"] is True
    assert (
        client.post(
            f"/api/music/releases/{release.pk}/office/not-real/", {}, format="json"
        ).status_code
        == 400
    )
