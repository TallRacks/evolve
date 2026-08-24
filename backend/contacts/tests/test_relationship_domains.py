import uuid

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from audit.models import AuditEvent
from contacts.admin import ContactAdmin
from contacts.models import Contact
from organizations.models import Membership, Organization
from promoters.admin import PromoterAdmin, PromoterContactAdmin
from promoters.models import Promoter, PromoterContact
from promoters.services import add_promoter_contact
from users.models import User
from venues.admin import VenueAdmin, VenueContactAdmin
from venues.models import Venue, VenueContact
from venues.services import add_venue_contact
from white_label.services import create_api_client_key

pytestmark = pytest.mark.django_db
PASSWORD = "Test-only-credential-123"


@pytest.fixture
def org():
    return Organization.objects.create(name="Relationships", slug="relationships")


@pytest.fixture
def other_org():
    return Organization.objects.create(name="Other", slug="other-relationships")


@pytest.fixture
def owner(org):
    user = User.objects.create_user(email="relationship-owner@example.invalid", password=PASSWORD)
    Membership.objects.create(user=user, organization=org, role=Membership.Role.OWNER)
    return user


@pytest.fixture
def manager(org):
    user = User.objects.create_user(email="relationship-manager@example.invalid", password=PASSWORD)
    Membership.objects.create(user=user, organization=org, role=Membership.Role.MANAGER)
    return user


@pytest.fixture
def member(org):
    user = User.objects.create_user(email="relationship-member@example.invalid", password=PASSWORD)
    Membership.objects.create(user=user, organization=org, role=Membership.Role.MEMBER)
    return user


@pytest.fixture
def superuser():
    return User.objects.create_superuser(
        email="relationship-platform@example.invalid", password=PASSWORD
    )


@pytest.fixture
def contact(org):
    return Contact.objects.create(
        organization=org, first_name="Taylor", last_name="Example", email="taylor@example.invalid"
    )


@pytest.fixture
def promoter(org):
    return Promoter.objects.create(
        organization=org, name="North Promotions", slug="north-promotions"
    )


@pytest.fixture
def venue(org):
    return Venue.objects.create(
        organization=org,
        name="Signal Hall",
        slug="signal-hall",
        city="Cape Town",
        country="South Africa",
    )


def test_models_use_uuid_and_scoped_slugs(org, other_org):
    contact = Contact.objects.create(organization=org, first_name="A", last_name="Person")
    promoter = Promoter.objects.create(organization=org, name="Promoter", slug="shared")
    venue = Venue.objects.create(organization=org, name="Venue", slug="shared")
    assert all(isinstance(item.id, uuid.UUID) for item in (contact, promoter, venue))
    with pytest.raises(IntegrityError), transaction.atomic():
        Promoter.objects.create(organization=org, name="Duplicate", slug="shared")
    with pytest.raises(IntegrityError), transaction.atomic():
        Venue.objects.create(organization=org, name="Duplicate", slug="shared")
    assert Promoter.objects.create(organization=other_org, name="Allowed", slug="shared")
    assert Venue.objects.create(organization=other_org, name="Allowed", slug="shared")


def test_manager_can_create_and_mutations_are_audited(client, manager, org):
    client.force_login(manager)
    contact_response = client.post(
        "/api/contacts/",
        {"organization_id": str(org.id), "first_name": "Jamie", "last_name": "Stone"},
        content_type="application/json",
    )
    promoter_response = client.post(
        "/api/promoters/",
        {"organization_id": str(org.id), "name": "Live House", "slug": "live-house"},
        content_type="application/json",
    )
    venue_response = client.post(
        "/api/venues/",
        {"organization_id": str(org.id), "name": "City Hall", "slug": "city-hall"},
        content_type="application/json",
    )
    assert [
        contact_response.status_code,
        promoter_response.status_code,
        venue_response.status_code,
    ] == [201, 201, 201]
    assert set(AuditEvent.objects.values_list("action", flat=True)) >= {
        "contact.created",
        "promoter.created",
        "venue.created",
    }


def test_member_views_but_cannot_mutate(client, member, org, promoter, venue, contact):
    client.force_login(member)
    for path in ("contacts", "promoters", "venues"):
        assert client.get(f"/api/{path}/", {"organization_id": org.id}).status_code == 200
        assert (
            client.post(
                f"/api/{path}/", {"organization_id": str(org.id)}, content_type="application/json"
            ).status_code
            == 403
        )
    assert (
        client.patch(
            f"/api/promoters/{promoter.id}/", {"name": "Denied"}, content_type="application/json"
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/venues/{venue.id}/", {"name": "Denied"}, content_type="application/json"
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/contacts/{contact.id}/",
            {"first_name": "Denied"},
            content_type="application/json",
        ).status_code
        == 403
    )


def test_cross_org_and_staff_only_access_is_hidden(client, owner, other_org):
    promoter = Promoter.objects.create(organization=other_org, name="Other", slug="other")
    venue = Venue.objects.create(organization=other_org, name="Other", slug="other")
    contact = Contact.objects.create(organization=other_org, first_name="Other", last_name="Person")
    client.force_login(owner)
    for path in (f"promoters/{promoter.id}", f"venues/{venue.id}", f"contacts/{contact.id}"):
        assert client.get(f"/api/{path}/").status_code == 404
    staff = User.objects.create_user(
        email="staff-only@example.invalid", password=PASSWORD, is_staff=True
    )
    client.force_login(staff)
    assert client.get(f"/api/promoters/{promoter.id}/").status_code == 404


def test_platform_superuser_cross_org_create(client, superuser, other_org):
    client.force_login(superuser)
    assert (
        client.post(
            "/api/platform/promoters/",
            {
                "organization_id": str(other_org.id),
                "name": "Platform Promoter",
                "slug": "platform-promoter",
            },
            content_type="application/json",
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/platform/venues/",
            {
                "organization_id": str(other_org.id),
                "name": "Platform Venue",
                "slug": "platform-venue",
            },
            content_type="application/json",
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/platform/contacts/",
            {
                "organization_id": str(other_org.id),
                "first_name": "Platform",
                "last_name": "Contact",
            },
            content_type="application/json",
        ).status_code
        == 201
    )


def test_lifecycle_updates_and_audit(client, manager, promoter, venue, contact):
    client.force_login(manager)
    assert (
        client.patch(
            f"/api/promoters/{promoter.id}/",
            {"status": "inactive"},
            content_type="application/json",
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/venues/{venue.id}/", {"status": "inactive"}, content_type="application/json"
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/contacts/{contact.id}/", {"is_active": False}, content_type="application/json"
        ).status_code
        == 200
    )
    assert set(AuditEvent.objects.values_list("action", flat=True)) >= {
        "promoter.deactivated",
        "venue.deactivated",
        "contact.deactivated",
    }


def test_relationship_same_org_cross_org_duplicate_and_inactive(
    owner, org, other_org, promoter, venue, contact
):
    promoter_link = add_promoter_contact(
        actor=owner,
        promoter=promoter,
        contact=contact,
        data={"responsibility": "promoter", "is_primary": True},
    )
    venue_link = add_venue_contact(
        actor=owner,
        venue=venue,
        contact=contact,
        data={"responsibility": "venue_manager", "is_primary": True},
    )
    assert promoter_link.is_primary and venue_link.is_primary
    with pytest.raises(ValidationError):
        add_promoter_contact(
            actor=owner, promoter=promoter, contact=contact, data={"responsibility": "general"}
        )
    cross = Contact.objects.create(organization=other_org, first_name="Cross", last_name="Org")
    with pytest.raises(ValidationError):
        add_promoter_contact(
            actor=owner, promoter=promoter, contact=cross, data={"responsibility": "general"}
        )
    with pytest.raises(ValidationError):
        add_venue_contact(
            actor=owner, venue=venue, contact=cross, data={"responsibility": "general"}
        )
    contact.is_active = False
    contact.save(update_fields=("is_active", "updated_at"))
    second_promoter = Promoter.objects.create(organization=org, name="Second", slug="second")
    with pytest.raises(ValidationError):
        add_promoter_contact(
            actor=owner,
            promoter=second_promoter,
            contact=contact,
            data={"responsibility": "general"},
        )


def test_relationship_api_authorization_removal_and_reactivation(
    client, owner, manager, promoter, venue, contact
):
    client.force_login(manager)
    first = client.post(
        f"/api/promoters/{promoter.id}/contacts/",
        {"contact_id": str(contact.id), "responsibility": "production"},
        content_type="application/json",
    )
    assert first.status_code == 201
    removed = client.patch(
        f"/api/promoters/{promoter.id}/contacts/{first.json()['id']}/",
        {"is_active": False},
        content_type="application/json",
    )
    assert removed.status_code == 200
    restored = client.post(
        f"/api/promoters/{promoter.id}/contacts/",
        {"contact_id": str(contact.id), "responsibility": "finance", "is_primary": True},
        content_type="application/json",
    )
    assert restored.status_code == 201 and restored.json()["id"] == first.json()["id"]
    client.force_login(owner)
    venue_link = client.post(
        f"/api/venues/{venue.id}/contacts/",
        {"contact_id": str(contact.id), "responsibility": "technical"},
        content_type="application/json",
    )
    assert venue_link.status_code == 201
    assert set(AuditEvent.objects.values_list("action", flat=True)) >= {
        "promoter.contact_added",
        "promoter.contact_removed",
        "venue.contact_added",
    }


def test_primary_per_role_constraint(org, promoter, contact):
    other = Contact.objects.create(organization=org, first_name="Other", last_name="Primary")
    PromoterContact.objects.create(
        promoter=promoter, contact=contact, responsibility="finance", is_primary=True
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        PromoterContact.objects.create(
            promoter=promoter, contact=other, responsibility="finance", is_primary=True
        )


def test_admin_relationship_validation_and_deletion_safeguards(
    org, other_org, owner, promoter, venue
):
    cross = Contact.objects.create(organization=other_org, first_name="Cross", last_name="Admin")
    with pytest.raises(ValidationError):
        PromoterContact(promoter=promoter, contact=cross).full_clean()
    with pytest.raises(ValidationError):
        VenueContact(venue=venue, contact=cross).full_clean()
    request = type("Request", (), {"user": owner})()
    for model_admin, model in (
        (ContactAdmin, Contact),
        (PromoterAdmin, Promoter),
        (PromoterContactAdmin, PromoterContact),
        (VenueAdmin, Venue),
        (VenueContactAdmin, VenueContact),
    ):
        assert not model_admin(model, admin.site).has_delete_permission(request)


def test_developer_scopes_and_organization_isolation(owner, org, other_org):
    Promoter.objects.create(organization=org, name="Visible", slug="visible")
    Promoter.objects.create(organization=other_org, name="Hidden", slug="hidden")
    Venue.objects.create(organization=org, name="Visible Venue", slug="visible")
    Venue.objects.create(organization=other_org, name="Hidden Venue", slug="hidden")
    _, promoter_key = create_api_client_key(
        organization=org,
        name="Promoters",
        description="",
        scopes=["promoter.read"],
        created_by=owner,
    )
    _, venue_key = create_api_client_key(
        organization=org, name="Venues", description="", scopes=["venue.read"], created_by=owner
    )
    _, denied = create_api_client_key(
        organization=org,
        name="Denied",
        description="",
        scopes=["organization.read"],
        created_by=owner,
    )
    from django.test import Client

    api = Client()
    promoter_response = api.get(
        "/api/developer/promoters/", HTTP_AUTHORIZATION=f"Bearer {promoter_key.secret}"
    )
    venue_response = api.get(
        "/api/developer/venues/", HTTP_AUTHORIZATION=f"Bearer {venue_key.secret}"
    )
    assert [item["name"] for item in promoter_response.json()] == ["Visible"]
    assert [item["name"] for item in venue_response.json()] == ["Visible Venue"]
    assert (
        api.get(
            "/api/developer/promoters/", HTTP_AUTHORIZATION=f"Bearer {denied.secret}"
        ).status_code
        == 403
    )
