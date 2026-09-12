import hashlib
from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from users.mobile_models import MobileCredential, MobileDevice

pytestmark = pytest.mark.django_db


def mobile_login(user):
    response = Client().post(
        reverse("users_api:mobile-login"),
        {"email": user.email, "password": "Correct-Horse-123", "platform": "ios"},
        content_type="application/json",
    )
    assert response.status_code == 200
    return response, response.json()["tokens"]


def test_mobile_login_returns_opaque_tokens_and_only_digests(user):
    response, tokens = mobile_login(user)
    assert response.json()["session"]["user"]["email"] == user.email
    assert len(tokens["access"]) > 40
    assert len(tokens["refresh"]) > 40
    assert not MobileCredential.objects.filter(token_digest=tokens["access"]).exists()
    assert MobileCredential.objects.filter(
        token_digest=hashlib.sha256(tokens["access"].encode()).hexdigest()
    ).exists()
    assert MobileCredential.objects.filter(
        token_digest=hashlib.sha256(tokens["refresh"].encode()).hexdigest()
    ).exists()


def test_mobile_access_logout_and_inactive_user_are_rejected(user):
    _, tokens = mobile_login(user)
    client = Client(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert client.get(reverse("users_api:mobile-me")).status_code == 200
    assert client.post(reverse("users_api:mobile-logout")).status_code == 204
    assert client.get(reverse("users_api:mobile-me")).status_code == 401

    _, tokens = mobile_login(user)
    user.is_active = False
    user.save(update_fields=("is_active", "updated_at"))
    assert (
        Client(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        .get(reverse("users_api:mobile-me"))
        .status_code
        == 401
    )


def test_refresh_rotates_and_reuse_revokes_device(user):
    _, tokens = mobile_login(user)
    response = Client().post(
        reverse("users_api:mobile-refresh"),
        {"refresh": tokens["refresh"]},
        content_type="application/json",
    )
    assert response.status_code == 200
    rotated = response.json()["tokens"]
    assert rotated["refresh"] != tokens["refresh"]
    old = Client().post(
        reverse("users_api:mobile-refresh"),
        {"refresh": tokens["refresh"]},
        content_type="application/json",
    )
    assert old.status_code == 401
    assert old.json()["code"] == "mobile_session_reused"
    assert (
        MobileDevice.objects.get(pk=response.json()["device"]["id"]).status
        == MobileDevice.Status.REVOKED
    )


def test_expired_refresh_and_logout_all(user):
    _, tokens = mobile_login(user)
    credential = MobileCredential.objects.get(
        token_digest=hashlib.sha256(tokens["refresh"].encode()).hexdigest()
    )
    credential.expires_at = timezone.now() - timedelta(seconds=1)
    credential.save(update_fields=("expires_at", "updated_at"))
    assert (
        Client()
        .post(
            reverse("users_api:mobile-refresh"),
            {"refresh": tokens["refresh"]},
            content_type="application/json",
        )
        .status_code
        == 401
    )

    _, tokens = mobile_login(user)
    client = Client(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert client.post(reverse("users_api:mobile-logout-all")).status_code == 204
    assert client.get(reverse("users_api:mobile-me")).status_code == 401


def test_browser_session_endpoint_does_not_accept_mobile_bearer(user):
    client = Client(HTTP_AUTHORIZATION="Bearer not-a-session")
    assert client.get(reverse("users_api:me")).status_code == 401
