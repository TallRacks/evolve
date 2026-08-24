import pytest
from django.contrib import admin
from django.test import RequestFactory

from organizations.admin import OrganizationAdmin
from organizations.models import Organization
from users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def use_unhashed_static_storage(settings):
    settings.STORAGES["staticfiles"] = {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    }


def test_platform_models_admin_requires_superuser(superuser):
    model_admin = OrganizationAdmin(Organization, admin.site)
    request = RequestFactory().get("/admin/")
    request.user = superuser
    assert model_admin.has_module_permission(request)

    request.user = User.objects.create_user(
        email="staff@example.com", password="Correct-Horse-123", is_staff=True
    )
    assert not model_admin.has_module_permission(request)
    assert not model_admin.has_view_permission(request)


def membership_change_url(membership):
    from django.urls import reverse

    return reverse("admin:organizations_membership_change", args=(membership.pk,))


def membership_change_data(membership, *, role=None, is_active=True):
    data = {
        "user": membership.user_id,
        "organization": membership.organization_id,
        "role": role or membership.role,
        "_save": "Save",
    }
    if is_active:
        data["is_active"] = "on"
    return data


def test_membership_admin_rejects_demotion_with_only_ineffective_other_owners(
    client, superuser, owner, organization
):
    from organizations.models import Membership

    inactive_user = User.objects.create_user(
        email="inactive-admin-owner@example.com",
        password="Correct-Horse-123",
        is_active=False,
    )
    Membership.objects.create(
        user=inactive_user,
        organization=organization,
        role=Membership.Role.OWNER,
        is_active=True,
    )
    inactive_membership_user = User.objects.create_user(
        email="suspended-admin-owner@example.com", password="Correct-Horse-123"
    )
    Membership.objects.create(
        user=inactive_membership_user,
        organization=organization,
        role=Membership.Role.OWNER,
        is_active=False,
    )
    membership = owner.memberships.get(organization=organization)
    client.force_login(superuser)
    response = client.post(
        membership_change_url(membership),
        membership_change_data(membership, role=Membership.Role.ADMIN),
    )
    assert response.status_code == 200
    assert "must retain at least one active owner" in response.content.decode()
    membership.refresh_from_db()
    assert membership.role == Membership.Role.OWNER
    assert membership.is_active


def test_membership_admin_allows_demotion_with_another_effective_owner(
    client, superuser, owner, organization
):
    from organizations.models import Membership

    other_owner = User.objects.create_user(
        email="effective-admin-owner@example.com", password="Correct-Horse-123"
    )
    Membership.objects.create(
        user=other_owner,
        organization=organization,
        role=Membership.Role.OWNER,
        is_active=True,
    )
    membership = owner.memberships.get(organization=organization)
    client.force_login(superuser)
    response = client.post(
        membership_change_url(membership),
        membership_change_data(membership, role=Membership.Role.ADMIN),
    )
    assert response.status_code == 302
    membership.refresh_from_db()
    assert membership.role == Membership.Role.ADMIN


def test_membership_admin_rejects_final_owner_deactivation(client, superuser, owner, organization):
    membership = owner.memberships.get(organization=organization)
    client.force_login(superuser)
    response = client.post(
        membership_change_url(membership),
        membership_change_data(membership, is_active=False),
    )
    assert response.status_code == 200
    membership.refresh_from_db()
    assert membership.is_active
