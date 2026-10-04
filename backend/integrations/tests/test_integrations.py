from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from integrations.models import EmailConnector, StorageProvider
from integrations.services import _smtp
from integrations.validation import (
    validate_email_secret_reference,
    validate_path_prefix,
    validate_secret_reference,
    validate_storage_endpoint,
    validate_storage_secret_reference,
)
from users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def super_client():
    user = User.objects.create_superuser("platform@example.test", "Test-only-platform-password-123")
    client = APIClient()
    client.force_authenticate(user)
    return client


def email_payload():
    return {
        "name": "Primary",
        "provider_type": "smtp",
        "from_name": "Evolve",
        "from_email": "noreply@example.test",
        "reply_to_email": "",
        "host": "smtp.example.test",
        "port": 587,
        "use_tls": True,
        "use_ssl": False,
        "username": "evolve",
        "secret_reference": "EVOLVE_EMAIL_PRIMARY_PASSWORD",
    }


def storage_payload():
    return {
        "name": "Primary storage",
        "provider_type": "s3_compatible",
        "endpoint": "https://objects.example.test",
        "region": "af-south-1",
        "bucket": "evolve-private-test",
        "path_prefix": "evolve",
        "public_base_url": "",
        "access_key_reference": "EVOLVE_STORAGE_ACCESS_KEY",
        "secret_key_reference": "EVOLVE_STORAGE_SECRET_KEY",
        "use_ssl": True,
    }


def test_platform_configuration_is_superuser_only(super_client):
    assert (
        super_client.post(
            "/api/platform/email-connectors/", email_payload(), format="json"
        ).status_code
        == 201
    )
    staff = User.objects.create_user(
        "staff@example.test", "Test-only-staff-password-123", is_staff=True
    )
    client = APIClient()
    client.force_authenticate(staff)
    assert client.get("/api/platform/email-connectors/").status_code == 403
    assert client.get("/api/platform/storage/").status_code == 403


def test_email_lifecycle_and_test_never_serialize_secret(super_client):
    created = super_client.post(
        "/api/platform/email-connectors/", email_payload(), format="json"
    ).json()
    assert "password" not in created
    assert created["secret_configured"] is False
    pk = created["id"]
    assert (
        super_client.post(
            f"/api/platform/email-connectors/{pk}/activate/", {}, format="json"
        ).status_code
        == 200
    )
    assert (
        super_client.post(
            f"/api/platform/email-connectors/{pk}/set-default/", {}, format="json"
        ).status_code
        == 200
    )
    with patch("integrations.api.views.test_email_connector"):
        assert (
            super_client.post(
                f"/api/platform/email-connectors/{pk}/test/", {}, format="json"
            ).status_code
            == 200
        )


def test_storage_validation_and_lifecycle(super_client):
    created = super_client.post("/api/platform/storage/", storage_payload(), format="json")
    assert created.status_code == 201
    assert "credentials_configured" in created.json()
    assert "access_key" not in created.json()
    pk = created.json()["id"]
    assert (
        super_client.post(f"/api/platform/storage/{pk}/activate/", {}, format="json").status_code
        == 200
    )
    with patch("integrations.api.views.test_storage_provider"):
        assert (
            super_client.post(f"/api/platform/storage/{pk}/test/", {}, format="json").status_code
            == 200
        )


@pytest.mark.parametrize("value", ["../../secret", "/tmp/key", "email/primary", "$(SECRET)"])
def test_secret_references_reject_paths_and_expressions(value):
    with pytest.raises(ValidationError):
        validate_secret_reference(value)


def test_storage_rejects_traversal_and_private_endpoints():
    with pytest.raises(ValidationError):
        validate_path_prefix("../private")
    with pytest.raises(ValidationError):
        validate_storage_endpoint("http://objects.example.test")
    with pytest.raises(ValidationError):
        validate_storage_endpoint("https://127.0.0.1")


def test_unfold_admin_has_no_staff_bypass():
    from django.contrib import admin
    from django.contrib.auth.models import Permission

    staff = User.objects.create_user(
        "admin-staff@example.test", "Test-only-staff-password-123", is_staff=True
    )
    staff.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="integrations", codename="view_emailconnector"
        )
    )
    request = type("Request", (), {"user": User.objects.get(pk=staff.pk)})()
    assert not admin.site._registry[EmailConnector].has_view_permission(request)
    assert not admin.site._registry[StorageProvider].has_view_permission(request)


def test_secret_reference_namespaces_cannot_cross_domains():
    with pytest.raises(ValidationError):
        validate_email_secret_reference("EVOLVE_STORAGE_PRIMARY_SECRET")
    with pytest.raises(ValidationError):
        validate_storage_secret_reference("EVOLVE_EMAIL_PRIMARY_PASSWORD")


def test_smtp_relay_allows_unauthenticated_connection(monkeypatch):
    connector = EmailConnector(
        name="Google relay", from_name="Evolve", from_email="bookings@example.test",
        host="smtp.example.test", port=587, use_tls=True, username="", secret_reference="",
    )
    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def starttls(self, context): pass
        def login(self, username, password): raise AssertionError("relay must not authenticate")
    monkeypatch.setattr("integrations.services.smtplib.SMTP", lambda *args, **kwargs: Client())
    assert _smtp(connector)
