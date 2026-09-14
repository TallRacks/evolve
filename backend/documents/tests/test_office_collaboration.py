import pytest
from rest_framework.test import APIClient

from documents.models import (
    Document,
    DocumentCollaborator,
    DocumentFavorite,
    DocumentRecentAccess,
    OfficeDocumentContent,
)
from documents.office_services import create_office_document
from documents.services import (
    archive_document,
    duplicate_office_document,
    move_document_to_workspace,
    restore_document,
)
from organizations.models import Membership, Organization
from users.models import User
from workspace.models import Workspace

pytestmark = pytest.mark.django_db


def make_fixture():
    organization = Organization.objects.create(name="Collaboration Org", slug="collaboration-org")
    owner = User.objects.create_user(
        email="owner-collab@example.invalid", password="test-password-123"
    )
    member = User.objects.create_user(
        email="member-collab@example.invalid", password="test-password-123"
    )
    Membership.objects.create(user=owner, organization=organization, role=Membership.Role.OWNER)
    Membership.objects.create(user=member, organization=organization, role=Membership.Role.MEMBER)
    document = create_office_document(
        actor=owner,
        organization=organization,
        title="Shared brief",
        document_type=Document.Type.OTHER,
        format=OfficeDocumentContent.Format.DOCUMENT,
        visibility=Document.Visibility.PRIVATE,
    )
    return owner, member, organization, document


def test_sharing_roles_control_editing_and_cross_org_isolation():
    owner, member, organization, document = make_fixture()
    owner_client, member_client = APIClient(), APIClient()
    owner_client.force_authenticate(owner)
    member_client.force_authenticate(member)
    response = owner_client.post(
        f"/api/documents/{document.pk}/office-sharing/",
        {"organization_id": organization.pk, "user_id": member.pk, "role": "comment"},
        format="json",
    )
    assert response.status_code == 200
    assert (
        member_client.get(
            f"/api/documents/{document.pk}/office-content/?organization_id={organization.pk}"
        ).status_code
        == 200
    )
    payload = {
        "organization_id": organization.pk,
        "content_json": {
            "type": "doc",
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "blocked"}]}],
        },
        "expected_revision": 0,
    }
    assert (
        member_client.patch(
            f"/api/documents/{document.pk}/office-content/", payload, format="json"
        ).status_code
        == 403
    )
    owner_client.patch(
        f"/api/documents/{document.pk}/office-sharing/",
        {"organization_id": organization.pk, "visibility": "restricted"},
        format="json",
    )
    collaborator = DocumentCollaborator.objects.get(document=document, user=member)
    owner_client.patch(
        f"/api/documents/{document.pk}/office-sharing/{collaborator.pk}/",
        {"organization_id": organization.pk, "role": "edit"},
        format="json",
    )
    assert (
        member_client.patch(
            f"/api/documents/{document.pk}/office-content/", payload, format="json"
        ).status_code
        == 200
    )
    other_org = Organization.objects.create(
        name="Other Collaboration Org", slug="other-collaboration-org"
    )
    assert (
        member_client.get(
            f"/api/documents/{document.pk}/office-content/?organization_id={other_org.pk}"
        ).status_code
        == 404
    )


def test_favorite_recent_duplicate_and_archive_lifecycle_are_persistent():
    owner, member, organization, document = make_fixture()
    client = APIClient()
    client.force_authenticate(member)
    DocumentCollaborator.objects.create(
        document=document, user=member, role=DocumentCollaborator.Role.VIEW, created_by=owner
    )
    assert (
        client.post(
            f"/api/documents/{document.pk}/office-favorite/",
            {"organization_id": organization.pk},
            format="json",
        ).json()["favorite"]
        is True
    )
    assert DocumentFavorite.objects.filter(user=member, document=document).exists()
    assert client.get(
        f"/api/office/documents/list/?organization_id={organization.pk}&favorite=true"
    ).json()[0]["id"] == str(document.pk)
    assert (
        client.get(
            f"/api/documents/{document.pk}/office-content/?organization_id={organization.pk}"
        ).status_code
        == 200
    )
    assert DocumentRecentAccess.objects.filter(user=member, document=document).exists()
    copy = duplicate_office_document(document, actor=owner)
    workspace = Workspace.objects.create(
        organization=organization, name="Ops", slug="ops", created_by=owner
    )
    move_document_to_workspace(copy, actor=owner, workspace=workspace)
    assert copy.__class__.objects.get(pk=copy.pk).workspace_id == workspace.pk
    archive_document(copy, actor=owner)
    assert restore_document(copy, actor=owner).status == Document.Status.ACTIVE
