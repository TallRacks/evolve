import pytest
from django.urls import reverse

from organizations.models import Membership, Organization
from users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def use_unhashed_static_storage(settings):
    settings.STORAGES["staticfiles"] = {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    }


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="User Admin Org", slug="user-admin-org")


@pytest.fixture
def owner(db, organization):
    user = User.objects.create_user(
        email="user-admin-owner@example.com", password="Correct-Horse-123"
    )
    Membership.objects.create(
        user=user,
        organization=organization,
        role=Membership.Role.OWNER,
        is_active=True,
    )
    return user


def user_change_data(user, *, is_active=True):
    data = {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "_save": "Save",
    }
    if is_active:
        data["is_active"] = "on"
    if user.is_staff:
        data["is_staff"] = "on"
    if user.is_superuser:
        data["is_superuser"] = "on"
    return data


def post_user_change(client, superuser, user, *, is_active):
    client.force_login(superuser)
    return client.post(
        reverse("admin:users_user_change", args=(user.pk,)),
        user_change_data(user, is_active=is_active),
    )


def test_user_admin_rejects_final_effective_owner_deactivation(
    client, superuser, owner, organization
):
    response = post_user_change(client, superuser, owner, is_active=False)
    assert response.status_code == 200
    assert "must retain at least one active owner" in response.content.decode()
    owner.refresh_from_db()
    assert owner.is_active


def test_user_admin_allows_deactivation_when_another_effective_owner_exists(
    client, superuser, owner, organization
):
    other_owner = User.objects.create_user(
        email="other-user-admin-owner@example.com", password="Correct-Horse-123"
    )
    Membership.objects.create(
        user=other_owner,
        organization=organization,
        role=Membership.Role.OWNER,
        is_active=True,
    )
    response = post_user_change(client, superuser, owner, is_active=False)
    assert response.status_code == 302
    owner.refresh_from_db()
    assert not owner.is_active


def test_user_admin_rejects_owner_deactivation_across_multiple_organizations(
    client, superuser, owner, organization
):
    other = Organization.objects.create(name="Second Admin Org", slug="second-admin-org")
    Membership.objects.create(
        user=owner,
        organization=other,
        role=Membership.Role.OWNER,
        is_active=True,
    )
    response = post_user_change(client, superuser, owner, is_active=False)
    assert response.status_code == 200
    content = response.content.decode()
    assert organization.name in content
    assert other.name in content
    owner.refresh_from_db()
    assert owner.is_active


def test_user_admin_allows_owner_deactivation_for_inactive_organization(
    client, superuser, owner, organization
):
    organization.is_active = False
    organization.save(update_fields=("is_active", "updated_at"))
    response = post_user_change(client, superuser, owner, is_active=False)
    assert response.status_code == 302
    owner.refresh_from_db()
    assert not owner.is_active
