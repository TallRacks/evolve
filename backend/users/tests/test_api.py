import pytest
from django.test import Client
from django.urls import reverse

from organizations.models import Membership, Organization
from users.models import User

pytestmark = pytest.mark.django_db


def csrf_client():
    client = Client(enforce_csrf_checks=True)
    response = client.get(reverse("users_api:csrf"))
    assert response.status_code == 204
    return client, response.cookies["csrftoken"].value


def test_login_requires_csrf(user):
    client = Client(enforce_csrf_checks=True)
    response = client.post(
        reverse("users_api:login"),
        {"email": user.email, "password": "Correct-Horse-123"},
        content_type="application/json",
    )
    assert response.status_code == 403


def test_valid_login_establishes_and_rotates_session(user):
    client, csrf_token = csrf_client()
    session = client.session
    session["pre_login"] = True
    session.save()
    previous_session_key = session.session_key

    response = client.post(
        reverse("users_api:login"),
        {"email": user.email, "password": "Correct-Horse-123"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == user.email
    assert response.json()["memberships"] == []
    assert client.session.session_key != previous_session_key
    assert client.session["_auth_user_id"] == str(user.pk)
    assert client.get(reverse("users_api:me")).status_code == 200


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("member@example.com", "wrong-password"),
        ("unknown@example.com", "wrong-password"),
    ],
)
def test_login_rejects_invalid_credentials_generically(user, email, password):
    client, csrf_token = csrf_client()
    response = client.post(
        reverse("users_api:login"),
        {"email": email, "password": password},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid email or password."}


def test_login_rejects_inactive_user_generically():
    User.objects.create_user(
        email="inactive@example.com", password="Correct-Horse-123", is_active=False
    )
    client, csrf_token = csrf_client()
    response = client.post(
        reverse("users_api:login"),
        {"email": "inactive@example.com", "password": "Correct-Horse-123"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid email or password."}


def test_logout_requires_authentication_and_invalidates_session(user):
    client, csrf_token = csrf_client()
    client.force_login(user)
    response = client.post(reverse("users_api:logout"), HTTP_X_CSRFTOKEN=csrf_token)
    assert response.status_code == 204
    assert client.get(reverse("users_api:me")).status_code == 401
    assert "_auth_user_id" not in client.session


def test_me_requires_authentication(client):
    response = client.get(reverse("users_api:me"))
    assert response.status_code == 401


def test_me_returns_safe_profile_and_only_active_memberships(client, user):
    active_org = Organization.objects.create(name="Active", slug="active")
    inactive_membership_org = Organization.objects.create(
        name="Inactive Membership", slug="inactive-membership"
    )
    inactive_org = Organization.objects.create(
        name="Inactive Org", slug="inactive", is_active=False
    )
    active = Membership.objects.create(
        user=user, organization=active_org, role=Membership.Role.ARTIST, is_active=True
    )
    Membership.objects.create(
        user=user,
        organization=inactive_membership_org,
        role=Membership.Role.ADMIN,
        is_active=False,
    )
    Membership.objects.create(
        user=user, organization=inactive_org, role=Membership.Role.OWNER, is_active=True
    )
    client.force_login(user)

    response = client.get(reverse("users_api:me"))

    assert response.status_code == 200
    assert response.json() == {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "first_name": "",
            "last_name": "",
            "is_superuser": False,
        },
        "memberships": [
            {
                "id": str(active.id),
                "organization": {
                    "id": str(active_org.id),
                    "name": "Active",
                    "slug": "active",
                },
                "role": Membership.Role.ARTIST,
                "permissions": ["organization.view", "portal.artist"],
            }
        ],
    }
    assert "password" not in str(response.json()).lower()


def test_me_identifies_superuser_without_fabricating_memberships(client, superuser):
    Organization.objects.create(name="Unrelated", slug="unrelated")
    client.force_login(superuser)
    response = client.get(reverse("users_api:me"))
    assert response.status_code == 200
    assert response.json()["user"]["is_superuser"] is True
    assert response.json()["memberships"] == []


def test_me_represents_multiple_active_organizations(client, user):
    organizations = [
        Organization.objects.create(name="First", slug="first"),
        Organization.objects.create(name="Second", slug="second"),
    ]
    for organization in organizations:
        Membership.objects.create(user=user, organization=organization)
    client.force_login(user)
    response = client.get(reverse("users_api:me"))
    assert response.status_code == 200
    assert {item["organization"]["slug"] for item in response.json()["memberships"]} == {
        "first",
        "second",
    }
