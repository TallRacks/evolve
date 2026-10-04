from datetime import date

import pytest
from django.core.exceptions import ValidationError

from artists.models import Artist
from bookings.services import create_booking
from documents.docx_services import render_generated_document_docx
from documents.models import DocumentTemplate, DocumentTemplateSection
from documents.pdf_services import render_generated_document_pdf
from documents.template_services import (
    add_template_section,
    generate_booking_document,
    render_template,
    set_template_status,
    update_template_section,
)
from organizations.models import Membership, Organization
from users.models import User

pytestmark = pytest.mark.django_db


def fixture_data():
    organization = Organization.objects.create(name="Template Org", slug="template-org")
    user = User.objects.create_user(
        email="templates@example.invalid", password="Template-test-password-123"
    )
    Membership.objects.create(user=user, organization=organization, role=Membership.Role.OWNER)
    artist = Artist.objects.create(organization=organization, stage_name="North", slug="north")
    booking = create_booking(
        actor=user,
        organization=organization,
        data={"title": "North Live", "artist": artist, "event_date": date(2026, 12, 1)},
    )
    template = DocumentTemplate.objects.create(
        organization=organization,
        name="Confirmation",
        key="confirmation",
        document_type=DocumentTemplate.Type.BOOKING_CONFIRMATION,
        created_by=user,
    )
    return user, organization, booking, template


def test_allowlist_blocks_traversal_code_environment_and_unmatched_syntax():
    _, _, _, template = fixture_data()
    for payload in (
        "{{ booking.__class__ }}",
        "{{ settings.SECRET_KEY }}",
        "{{ organization.name|safe }}",
        "{% load static %}",
    ):
        with pytest.raises(ValidationError):
            DocumentTemplateSection.objects.create(
                template=template, key=f"bad-{len(payload)}", title="Bad", body=payload
            )


def test_render_missing_values_and_generated_snapshot_remain_immutable():
    user, _, booking, template = fixture_data()
    section = add_template_section(
        actor=user,
        template=template,
        data={
            "key": "summary",
            "title": "{{ artist.name }}",
            "body": "{{ booking.reference }} at {{ venue.name }}",
            "sequence": 1,
        },
    )
    template = set_template_status(
        actor=user, template=template, status=DocumentTemplate.Status.ACTIVE
    )
    rendered, missing = render_template(template, {"artist.name": "North"})
    assert "North" in rendered
    assert "booking.reference" in missing
    document, _ = generate_booking_document(
        actor=user, template=template, booking=booking, title="Confirmation"
    )
    snapshot = document.rendered_content
    update_template_section(actor=user, section=section, data={"body": "Changed"})
    document.refresh_from_db()
    assert document.rendered_content == snapshot
    assert render_generated_document_pdf(document).startswith(b"%PDF")
    assert render_generated_document_docx(document).startswith(b"PK")
