from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from audit.models import AuditEvent
from documents.models import Document, OfficeDocumentAttachment
from documents.office_services import create_office_document, save_content
from documents.services import upload_document
from documents.tests.test_secure_files import FakeStorage, setup_access
from organizations.models import Membership, Organization
from tasks.models import Task
from users.models import User

pytestmark = pytest.mark.django_db


def office(user, organization, visibility=Document.Visibility.ORGANIZATION):
    return create_office_document(
        actor=user,
        organization=organization,
        title="Office brief",
        document_type=Document.Type.OTHER,
        format="document",
        visibility=visibility,
    )


def stored(user, organization, provider, name="image.png", content=b"\x89PNG\r\n\x1a\nvalid"):
    with (
        patch("documents.services.default_storage_provider", return_value=provider),
        patch("documents.services.get_storage_backend", return_value=FakeStorage()),
    ):
        return upload_document(
            actor=user,
            organization=organization,
            file=SimpleUploadedFile(
                name,
                content,
                content_type="image/png" if name.endswith(".png") else "application/pdf",
            ),
            title=name,
            document_type=Document.Type.ARTWORK if name.endswith(".png") else Document.Type.OTHER,
            visibility=Document.Visibility.ORGANIZATION,
        )


def test_office_attachment_link_remove_retains_file_and_cross_org_is_denied():
    user, organization, provider = setup_access(suffix="office-attachment")
    other_org = Organization.objects.create(
        name="Other attachment org", slug="other-attachment-org"
    )
    other = User.objects.create_user(
        email="other-attachment@example.invalid", password="test-password-123"
    )
    Membership.objects.create(user=other, organization=other_org, role=Membership.Role.OWNER)
    document = office(user, organization)
    attachment = stored(user, organization, provider)
    client = APIClient()
    client.force_authenticate(user)
    linked = client.post(
        f"/api/documents/{document.pk}/office-attachments/",
        {"organization_id": organization.pk, "attachment_id": attachment.pk},
        format="json",
    )
    assert linked.status_code == 201
    link_id = linked.json()["id"]
    assert OfficeDocumentAttachment.objects.filter(pk=link_id).exists()
    assert (
        client.get(
            f"/api/documents/{document.pk}/office-attachments/?organization_id={organization.pk}"
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/documents/{document.pk}/office-attachments/{link_id}/?organization_id={organization.pk}"
        ).status_code
        == 204
    )
    assert Document.objects.filter(pk=attachment.pk).exists()
    other_client = APIClient()
    other_client.force_authenticate(other)
    assert (
        other_client.get(
            f"/api/documents/{document.pk}/office-attachments/?organization_id={other_org.pk}"
        ).status_code
        == 404
    )


def test_office_attachment_upload_uses_private_storage_and_rejects_invalid_image():
    user, organization, provider = setup_access(suffix="office-upload")
    document = office(user, organization)
    client = APIClient()
    client.force_authenticate(user)
    backend = FakeStorage()
    with (
        patch("documents.services.default_storage_provider", return_value=provider),
        patch("documents.services.get_storage_backend", return_value=backend),
    ):
        response = client.post(
            f"/api/documents/{document.pk}/office-attachments/?organization_id={organization.pk}",
            {
                "file": SimpleUploadedFile(
                    "photo.png", b"\x89PNG\r\n\x1a\nvalid", content_type="image/png"
                ),
                "is_image": "true",
            },
            format="multipart",
        )
    assert response.status_code == 201
    assert response.json()["is_image"] is True
    bad = client.post(
        f"/api/documents/{document.pk}/office-attachments/?organization_id={organization.pk}",
        {
            "file": SimpleUploadedFile(
                "bad.pdf", b"%PDF-1.7\nprivate", content_type="application/pdf"
            ),
            "is_image": "true",
        },
        format="multipart",
    )
    assert bad.status_code == 400


def test_image_nodes_require_authorized_internal_image_attachment_and_preserve_alt():
    user, organization, provider = setup_access(suffix="office-image")
    document = office(user, organization)
    attachment = stored(user, organization, provider)
    link = OfficeDocumentAttachment.objects.create(
        office_document=document, attachment=attachment, created_by=user, is_image=True
    )
    save_content(
        actor=user,
        document=document,
        content={
            "type": "doc",
            "content": [
                {"type": "image", "attrs": {"attachment_id": str(link.pk), "alt": "Tour artwork"}}
            ],
        },
        expected_revision=0,
    )
    with pytest.raises(ValidationError):
        save_content(
            actor=user,
            document=document,
            content={
                "type": "doc",
                "content": [
                    {"type": "image", "attrs": {"src": "javascript:alert(1)", "alt": "bad"}}
                ],
            },
            expected_revision=1,
        )
    with pytest.raises(ValidationError):
        save_content(
            actor=user,
            document=document,
            content={
                "type": "doc",
                "content": [
                    {
                        "type": "image",
                        "attrs": {"attachment_id": "00000000-0000-0000-0000-000000000000"},
                    }
                ],
            },
            expected_revision=1,
        )


def test_document_task_persists_source_and_audits_without_body_dump():
    user, organization, _ = setup_access(suffix="office-task")
    document = office(user, organization)
    client = APIClient()
    client.force_authenticate(user)
    response = client.post(
        f"/api/documents/{document.pk}/office-task/?organization_id={organization.pk}",
        {"title": "Confirm show details", "description": "Selected context", "priority": "high"},
        format="json",
    )
    assert response.status_code == 201
    task = Task.objects.get(pk=response.json()["id"])
    assert task.source_document_id == document.pk
    event = AuditEvent.objects.get(resource_id=str(task.pk), action="task.created")
    assert "Selected context" not in event.description
    assert client.get(f"/api/tasks/{task.pk}/").status_code == 200


def test_document_task_rejects_staff_and_cross_org_source():
    user, organization, _ = setup_access(suffix="office-task-scope")
    document = office(user, organization)
    staff = User.objects.create_user(
        email="office-staff@example.invalid", password="test-password-123", is_staff=True
    )
    client = APIClient()
    client.force_authenticate(staff)
    assert (
        client.post(
            f"/api/documents/{document.pk}/office-task/?organization_id={organization.pk}",
            {"title": "No"},
            format="json",
        ).status_code
        == 404
    )
