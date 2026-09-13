import pytest
from django.core.exceptions import ValidationError

from documents.models import Document, DocumentRevision, OfficeDocumentContent
from documents.office_services import create_office_document, restore_revision, save_content
from organizations.models import Membership, Organization
from users.models import User

pytestmark = pytest.mark.django_db


def setup_data():
    organization = Organization.objects.create(name="Office Org", slug="office-org")
    user = User.objects.create_user(
        email="office@example.invalid", password="Office-test-password-123"
    )
    Membership.objects.create(user=user, organization=organization, role=Membership.Role.OWNER)
    return user, organization


def test_native_document_save_conflict_and_restore():
    user, organization = setup_data()
    document = create_office_document(
        actor=user,
        organization=organization,
        title="Brief",
        document_type=Document.Type.OTHER,
        format=OfficeDocumentContent.Format.DOCUMENT,
        visibility=Document.Visibility.ORGANIZATION,
    )
    first = {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "One"}]}],
    }
    save_content(actor=user, document=document, content=first, expected_revision=0)
    with pytest.raises(ValueError, match="CONFLICT"):
        save_content(actor=user, document=document, content=first, expected_revision=0)
    restored = restore_revision(actor=user, document=document, revision_number=1)
    assert restored.revision_number == 2
    assert DocumentRevision.objects.filter(document=document).count() == 2


def test_sheet_starts_with_structured_sheet_content():
    user, organization = setup_data()
    document = create_office_document(
        actor=user, organization=organization, title="Sheet",
        document_type=Document.Type.OTHER, format=OfficeDocumentContent.Format.SHEET,
        visibility=Document.Visibility.ORGANIZATION,
    )
    assert document.office_content.content_json == {"type": "sheet", "columns": [], "rows": []}


def test_native_content_rejects_unsafe_nodes():
    user, organization = setup_data()
    document = create_office_document(
        actor=user,
        organization=organization,
        title="Safe",
        document_type=Document.Type.OTHER,
        format=OfficeDocumentContent.Format.DOCUMENT,
        visibility=Document.Visibility.ORGANIZATION,
    )
    with pytest.raises(ValidationError):
        save_content(
            actor=user,
            document=document,
            content={"type": "script", "text": "alert(1)"},
            expected_revision=0,
        )
