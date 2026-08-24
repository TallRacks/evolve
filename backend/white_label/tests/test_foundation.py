from datetime import timedelta

import pytest
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from audit.models import AuditEvent
from users.models import User
from white_label.admin import APIKeyAdmin
from white_label.models import APIKey, OrganizationBranding, OrganizationDomain
from white_label.services import (
    authenticate_api_key,
    create_api_client_key,
    create_domain,
    effective_branding,
)

pytestmark = pytest.mark.django_db


def branding_url(organization):
    return reverse("organization-branding", args=(organization.id,))


def clients_url(organization):
    return reverse("api-clients", args=(organization.id,))


def test_default_and_organization_branding(owner, organization):
    assert effective_branding(organization)["brand_name"] == organization.name
    branding = OrganizationBranding.objects.create(
        organization=organization, display_name="Studio Portal", primary_color="#123ABC"
    )
    effective = effective_branding(organization)
    assert effective["brand_name"] == "Studio Portal"
    assert effective["primary"] == "#123ABC"
    assert "custom_css" not in effective
    assert branding.organization == organization


def test_branding_get_does_not_create_configuration(client, owner, organization):
    client.force_login(owner)
    assert client.get(branding_url(organization)).status_code == 200
    assert not OrganizationBranding.objects.filter(organization=organization).exists()


@pytest.mark.parametrize("actor_fixture", ["owner", "admin_user"])
def test_owner_and_admin_can_update_branding(request, client, actor_fixture, organization):
    actor = request.getfixturevalue(actor_fixture)
    client.force_login(actor)
    response = client.patch(
        branding_url(organization),
        {"display_name": "New Brand", "primary_color": "#E0B84B"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert AuditEvent.objects.filter(action="branding.updated", actor=actor).exists()


def test_branding_rejects_inaccessible_contrast(client, owner, organization):
    client.force_login(owner)
    response = client.patch(
        branding_url(organization),
        {"primary_color": "#111111", "background_color": "#000000"},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "primary_color" in response.json()


def test_member_invalid_color_and_cross_org_branding_are_denied(
    client, owner, member, organization, other_organization
):
    client.force_login(member)
    assert (
        client.patch(
            branding_url(organization), {"display_name": "Denied"}, content_type="application/json"
        ).status_code
        == 403
    )
    client.force_login(owner)
    assert client.get(branding_url(other_organization)).status_code == 404
    assert (
        client.patch(
            branding_url(organization), {"primary_color": "red"}, content_type="application/json"
        ).status_code
        == 400
    )


def test_superuser_can_manage_branding_cross_organization(client, superuser, organization):
    client.force_login(superuser)
    response = client.patch(
        branding_url(organization),
        {"display_name": "Platform Managed"},
        content_type="application/json",
    )
    assert response.status_code == 200


def test_domain_normalization_validation_duplicate_and_activation(organization):
    domain = create_domain(organization=organization, hostname="Portal.Example.COM.")
    assert domain.hostname == "portal.example.com"
    assert domain.verification_name == "_evolve-verification.portal.example.com"
    assert len(domain.verification_token) >= 32
    with pytest.raises(ValidationError):
        create_domain(organization=organization, hostname="https://bad.example.com/path")
    with pytest.raises((ValidationError, IntegrityError)):
        create_domain(organization=organization, hostname="portal.example.com")
    domain.is_active = True
    with pytest.raises(ValidationError):
        domain.full_clean()


def test_domain_api_scoping_and_platform_lifecycle(
    client, owner, member, superuser, organization, other_organization
):
    url = reverse("organization-domains", args=(organization.id,))
    client.force_login(member)
    assert client.post(url, {"hostname": "member.example.com"}).status_code == 403
    client.force_login(owner)
    created = client.post(url, {"hostname": "brand.example.com"}, content_type="application/json")
    assert created.status_code == 201
    assert AuditEvent.objects.filter(action="domain.created").exists()
    assert AuditEvent.objects.filter(action="domain.verification_requested").exists()
    assert (
        client.get(reverse("organization-domains", args=(other_organization.id,))).status_code
        == 404
    )
    domain_id = created.json()["id"]
    client.force_login(superuser)
    detail = reverse("platform-domain-detail", args=(domain_id,))
    assert (
        client.patch(detail, {"action": "activate"}, content_type="application/json").status_code
        == 403
    )
    assert (
        client.patch(detail, {"action": "verify"}, content_type="application/json").status_code
        == 200
    )
    activated = client.patch(
        detail, {"action": "activate", "is_primary": True}, content_type="application/json"
    )
    assert activated.status_code == 200
    assert activated.json()["is_primary"] is True


def test_primary_domain_uniqueness(organization):
    first = create_domain(organization=organization, hostname="first.example.com")
    second = create_domain(organization=organization, hostname="second.example.com")
    for domain in (first, second):
        domain.verification_status = OrganizationDomain.VerificationStatus.VERIFIED
        domain.is_active = True
        domain.is_primary = True
    first.save()
    with pytest.raises(IntegrityError):
        second.save()


def test_api_secret_is_returned_once_hashed_and_lists_are_safe(client, owner, organization):
    client.force_login(owner)
    response = client.post(
        clients_url(organization),
        {"name": "Reporting", "description": "Read integration", "scopes": ["organization.read"]},
        content_type="application/json",
    )
    assert response.status_code == 201
    raw = response.json()["secret"]
    key = APIKey.objects.get()
    assert raw not in key.secret_digest
    listed = client.get(clients_url(organization)).json()
    assert "secret" not in str(listed).lower()
    assert key.key_prefix in str(listed)
    assert raw not in str(AuditEvent.objects.filter(action="api.key_created").values())


def test_api_key_authentication_lifecycle_and_scope(owner, organization):
    client_model, created = create_api_client_key(
        organization=organization,
        name="Test",
        description="",
        scopes=["organization.read"],
        created_by=owner,
    )
    assert authenticate_api_key(created.secret).pk == created.key.pk
    with pytest.raises(PermissionDenied):
        authenticate_api_key("evolve_invalid_secret")
    with pytest.raises(PermissionDenied):
        authenticate_api_key(created.secret, required_scope="team.read")
    created.key.revoked_at = timezone.now()
    created.key.save(update_fields=("revoked_at",))
    with pytest.raises(PermissionDenied):
        authenticate_api_key(created.secret)
    created.key.revoked_at = None
    created.key.expires_at = timezone.now() - timedelta(seconds=1)
    created.key.save(update_fields=("revoked_at", "expires_at"))
    with pytest.raises(PermissionDenied):
        authenticate_api_key(created.secret)
    created.key.expires_at = None
    created.key.save(update_fields=("expires_at",))
    client_model.is_active = False
    client_model.save(update_fields=("is_active", "updated_at"))
    with pytest.raises(PermissionDenied):
        authenticate_api_key(created.secret)


def test_whoami_and_key_management_permissions(client, owner, member, organization):
    _, created = create_api_client_key(
        organization=organization,
        name="Who",
        description="",
        scopes=["organization.read"],
        created_by=owner,
    )
    whoami = reverse("developer-whoami")
    assert client.get(whoami, HTTP_AUTHORIZATION=f"Bearer {created.secret}").status_code == 200
    assert client.get(whoami, HTTP_AUTHORIZATION="Bearer invalid").status_code == 403
    client.force_login(member)
    assert client.get(clients_url(organization)).status_code == 403


def test_staff_cannot_cross_org_but_superuser_can_manage_api_clients(
    client, superuser, organization
):
    staff = User.objects.create_user(
        email="wl-staff@example.com", password="Correct-Horse-123", is_staff=True
    )
    client.force_login(staff)
    assert client.get(clients_url(organization)).status_code == 404
    client.force_login(superuser)
    assert (
        client.post(
            clients_url(organization),
            {"name": "Platform", "scopes": ["profile.read"]},
            content_type="application/json",
        ).status_code
        == 201
    )


def test_api_key_admin_never_exposes_digest():
    model_admin = APIKeyAdmin(APIKey, admin.site)
    assert "secret_digest" in model_admin.exclude
    assert not model_admin.has_add_permission(type("Request", (), {})())
    assert not model_admin.has_change_permission(type("Request", (), {})())


def test_verified_primary_domain_resolves_but_unknown_host_does_not(organization):
    from white_label.services import organization_for_host

    domain = create_domain(organization=organization, hostname="tenant.example.com")
    domain.verification_status = OrganizationDomain.VerificationStatus.VERIFIED
    domain.verified_at = timezone.now()
    domain.is_active = True
    domain.is_primary = True
    domain.save()
    assert organization_for_host("TENANT.example.com:443") == organization
    assert organization_for_host("unknown.example.com") is None


def test_platform_branding_detail_and_api_client_deactivation(
    client, superuser, owner, organization
):
    client.force_login(superuser)
    branding_path = reverse("platform-branding-detail", args=(organization.id,))
    assert (
        client.patch(
            branding_path,
            {"display_name": "Platform Brand", "accent_color": "#ABCDEF"},
            content_type="application/json",
        ).status_code
        == 200
    )
    api_client, _ = create_api_client_key(
        organization=organization,
        name="Deactivate",
        description="",
        scopes=["organization.read"],
        created_by=owner,
    )
    detail = reverse("api-client-detail", args=(organization.id, api_client.id))
    assert client.post(detail).status_code == 204
    api_client.refresh_from_db()
    assert not api_client.is_active
    assert AuditEvent.objects.filter(action="api.client_deactivated").exists()
