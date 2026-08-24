import pytest
from django.urls import reverse

from organizations.models import Membership, Organization

pytestmark = pytest.mark.django_db


def test_me_requires_authentication(client):
    response = client.get(reverse("users_api:me"))
    assert response.status_code == 401


def test_me_returns_safe_user_and_only_active_memberships(client, user):
    active_org = Organization.objects.create(name="Active", slug="active")
    inactive_org = Organization.objects.create(
        name="Inactive Membership", slug="inactive-membership"
    )
    Membership.objects.create(
        user=user, organization=active_org, role=Membership.Role.MEMBER, is_active=True
    )
    Membership.objects.create(
        user=user, organization=inactive_org, role=Membership.Role.ADMIN, is_active=False
    )
    client.force_login(user)
    response = client.get(reverse("users_api:me"))
    assert response.status_code == 200
    assert response.json()["email"] == user.email
    assert response.json()["memberships"] == [
        {
            "id": str(user.memberships.get(organization=active_org).id),
            "organization_id": str(active_org.id),
            "organization_name": "Active",
            "organization_slug": "active",
            "role": Membership.Role.MEMBER,
        }
    ]
    assert "password" not in response.json()
