import pytest
from rest_framework.test import APIClient

from integrations.models import StoragePolicy
from organizations.models import Membership, Organization
from users.models import User
from workspace.models import Board, Workspace
from workspace.summary_services import workspace_summary

pytestmark = pytest.mark.django_db


def member_context():
    organization = Organization.objects.create(name="Workspace Org", slug="workspace-org")
    user = User.objects.create_user(email="member@workspace.test", password="Correct-Horse-123")
    Membership.objects.create(user=user, organization=organization, role=Membership.Role.ADMIN)
    client = APIClient()
    client.force_authenticate(user)
    return organization, user, client


def test_workspace_and_board_are_organization_scoped():
    organization, user, client = member_context()
    created = client.post("/api/workspaces/", {"organization_id": str(organization.id), "name": "Live Operations", "slug": "live-operations"}, format="json")
    assert created.status_code == 201
    workspace_id = created.json()["id"]
    board = client.post(f"/api/workspaces/{workspace_id}/boards/", {"name": "Bookings", "source_type": "bookings", "default_view": "board"}, format="json")
    assert board.status_code == 201
    assert "artist" in board.json()["allowed_fields"]
    assert client.post(f"/api/workspaces/{workspace_id}/boards/", {"name": "Unsafe", "source_type": "arbitrary"}, format="json").status_code == 400
    other = Organization.objects.create(name="Other Org", slug="other-org")
    assert client.get(f"/api/workspaces/{Workspace.objects.create(organization=other, name='Hidden', slug='hidden').id}/summary/").status_code == 404
    assert workspace_summary(user=user, workspace=Workspace.objects.get(pk=workspace_id))["workspace"]["name"] == "Live Operations"


def test_storage_policy_is_superuser_only_and_has_hard_ceiling():
    organization, user, client = member_context()
    assert client.get("/api/platform/storage-policy/").status_code == 403
    root = User.objects.create_superuser(email="root@workspace.test", password="Correct-Horse-123")
    root_client = APIClient()
    root_client.force_authenticate(root)
    response = root_client.get("/api/platform/storage-policy/")
    assert response.status_code == 200
    assert response.json()["max_document_size_bytes"] == 25 * 1024 * 1024
    assert root_client.patch("/api/platform/storage-policy/", {"max_document_size_bytes": 101 * 1024 * 1024}, format="json").status_code == 400
    assert StoragePolicy.objects.count() == 1


def test_archived_workspace_is_readable_but_not_selectable_for_new_boards():
    organization, user, client = member_context()
    workspace = Workspace.objects.create(
        organization=organization, name="Archived", slug="archived", archived=True
    )
    assert client.get("/api/workspaces/", {"organization_id": organization.id}).json() == []
    assert client.get(f"/api/workspaces/{workspace.id}/").json()["archived"] is True
    assert client.post(
        f"/api/workspaces/{workspace.id}/boards/",
        {"name": "Blocked", "source_type": "tasks"},
        format="json",
    ).status_code == 400
    restored = client.patch(
        f"/api/workspaces/{workspace.id}/", {"archived": False}, format="json"
    )
    assert restored.status_code == 200 and restored.json()["archived"] is False
