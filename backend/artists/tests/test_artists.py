import uuid

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse

from artists.admin import ArtistAdmin, ArtistPortalLinkAdmin, ArtistTeamAssignmentAdmin
from artists.models import Artist, ArtistPortalLink, ArtistTeamAssignment
from artists.services import assign_team_member, create_artist, link_portal_user
from audit.models import AuditEvent
from organizations.models import Membership
from users.models import User
from white_label.services import create_api_client_key

TEST_PASSWORD = "Correct-Horse-123"

pytestmark = pytest.mark.django_db


def artist_data(**overrides):
    return {
        "stage_name": "Signal North",
        "legal_name": "Test Artist",
        "slug": "signal-north",
        "status": "active",
        "email": "artist@example.com",
        "city": "Cape Town",
        "country": "South Africa",
        **overrides,
    }


def test_artist_model_uses_uuid_and_organization_scoped_slug(
    organization, other_organization
):
    artist = Artist.objects.create(organization=organization, **artist_data())
    assert isinstance(artist.id, uuid.UUID)
    with pytest.raises(IntegrityError), transaction.atomic():
        Artist.objects.create(
            organization=organization, **artist_data(stage_name="Duplicate")
        )
    other = Artist.objects.create(organization=other_organization, **artist_data())
    assert other.slug == artist.slug


def test_owner_and_manager_create_artists_with_audit(
    client, owner, manager, organization
):
    url = reverse("artist-list")
    for actor, slug in ((owner, "owner-artist"), (manager, "manager-artist")):
        client.force_login(actor)
        response = client.post(
            url,
            {"organization_id": str(organization.id), **artist_data(slug=slug)},
            content_type="application/json",
        )
        assert response.status_code == 201
    assert AuditEvent.objects.filter(action="artist.created").count() == 2


def test_member_can_view_but_cannot_create_or_update(client, member, organization):
    artist = Artist.objects.create(organization=organization, **artist_data())
    client.force_login(member)
    assert (
        client.get(
            reverse("artist-list"), {"organization_id": organization.id}
        ).status_code
        == 200
    )
    assert (
        client.post(
            reverse("artist-list"),
            {"organization_id": str(organization.id), **artist_data(slug="denied")},
            content_type="application/json",
        ).status_code
        == 403
    )
    assert (
        client.patch(
            reverse("artist-detail", args=(artist.id,)),
            {"stage_name": "Denied"},
            content_type="application/json",
        ).status_code
        == 403
    )


def test_cross_organization_and_staff_only_access_denied(
    client, owner, other_organization
):
    artist = Artist.objects.create(organization=other_organization, **artist_data())
    client.force_login(owner)
    assert client.get(reverse("artist-detail", args=(artist.id,))).status_code == 404
    staff = User.objects.create_user(
        email="artist-staff@example.com", password=TEST_PASSWORD, is_staff=True
    )
    client.force_login(staff)
    assert client.get(reverse("artist-detail", args=(artist.id,))).status_code == 404


def test_superuser_cross_org_create_and_lifecycle_audit(
    client, superuser, other_organization
):
    client.force_login(superuser)
    created = client.post(
        reverse("platform-artist-list"),
        {"organization_id": str(other_organization.id), **artist_data()},
        content_type="application/json",
    )
    assert created.status_code == 201
    detail = reverse("platform-artist-detail", args=(created.json()["id"],))
    assert (
        client.patch(
            detail, {"status": "archived"}, content_type="application/json"
        ).status_code
        == 200
    )
    assert AuditEvent.objects.filter(action="artist.archived").exists()


def test_team_assignment_same_org_inactive_duplicate_and_primary_rules(
    owner, organization, other_organization
):
    artist = create_artist(actor=owner, organization=organization, data=artist_data())
    membership = Membership.objects.get(user=owner, organization=organization)
    assignment = assign_team_member(
        actor=owner,
        artist=artist,
        membership=membership,
        data={"responsibility": "manager", "is_primary": True},
    )
    assert assignment.is_primary
    with pytest.raises(ValidationError):
        assign_team_member(
            actor=owner,
            artist=artist,
            membership=Membership.objects.create(
                user=User.objects.create_user(
                    email="cross@example.com", password=TEST_PASSWORD
                ),
                organization=other_organization,
                role=Membership.Role.MEMBER,
            ),
            data={"responsibility": "general"},
        )
    inactive = Membership.objects.create(
        user=User.objects.create_user(
            email="inactive@example.com", password=TEST_PASSWORD
        ),
        organization=organization,
        role=Membership.Role.MEMBER,
        is_active=False,
    )
    with pytest.raises(ValidationError):
        assign_team_member(
            actor=owner,
            artist=artist,
            membership=inactive,
            data={"responsibility": "general"},
        )
    with pytest.raises((ValidationError, IntegrityError)):
        assign_team_member(
            actor=owner,
            artist=artist,
            membership=membership,
            data={"responsibility": "general"},
        )


def test_team_api_authorization_and_removal_audit(client, owner, manager, organization):
    artist = Artist.objects.create(organization=organization, **artist_data())
    manager_membership = Membership.objects.get(user=manager, organization=organization)
    client.force_login(manager)
    assert (
        client.post(
            reverse("artist-team", args=(artist.id,)),
            {"membership_id": str(manager_membership.id), "responsibility": "manager"},
            content_type="application/json",
        ).status_code
        == 403
    )
    client.force_login(owner)
    created = client.post(
        reverse("artist-team", args=(artist.id,)),
        {"membership_id": str(manager_membership.id), "responsibility": "manager"},
        content_type="application/json",
    )
    assert created.status_code == 201
    response = client.patch(
        reverse("artist-team-detail", args=(artist.id, created.json()["id"])),
        {"is_active": False},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert AuditEvent.objects.filter(
        action="artist.team_removed", resource_id=str(artist.id)
    ).exists()


def test_portal_link_requires_membership_and_artist_role_for_portal(
    client, owner, member, artist_user, organization
):
    artist = Artist.objects.create(organization=organization, **artist_data())
    link_portal_user(
        actor=owner, artist=artist, user=artist_user, relationship="artist"
    )
    client.force_login(artist_user)
    response = client.get(reverse("artist-portal"))
    assert response.status_code == 200 and response.json()[0]["id"] == str(artist.id)
    link_portal_user(actor=owner, artist=artist, user=member, relationship="assistant")
    client.force_login(member)
    assert client.get(reverse("artist-portal")).json() == []
    outsider = User.objects.create_user(
        email="outsider@example.com", password=TEST_PASSWORD
    )
    with pytest.raises(ValidationError):
        link_portal_user(
            actor=owner, artist=artist, user=outsider, relationship="artist"
        )


def test_multiple_artist_portal_links_and_unlinked_user(
    client, owner, artist_user, organization
):
    for index in range(2):
        artist = Artist.objects.create(
            organization=organization,
            **artist_data(stage_name=f"Artist {index}", slug=f"artist-{index}"),
        )
        ArtistPortalLink.objects.create(artist=artist, user=artist_user)
    client.force_login(artist_user)
    assert len(client.get(reverse("artist-portal")).json()) == 2
    unlinked = User.objects.create_user(
        email="unlinked-artist@example.com", password=TEST_PASSWORD
    )
    Membership.objects.create(
        user=unlinked, organization=organization, role=Membership.Role.ARTIST
    )
    client.force_login(unlinked)
    assert client.get(reverse("artist-portal")).json() == []


def test_developer_artist_scope_and_organization_isolation(
    owner, organization, other_organization
):
    Artist.objects.create(organization=organization, **artist_data())
    Artist.objects.create(
        organization=other_organization, **artist_data(stage_name="Other")
    )
    _, allowed = create_api_client_key(
        organization=organization,
        name="Artists",
        description="",
        scopes=["artist.read"],
        created_by=owner,
    )
    _, denied = create_api_client_key(
        organization=organization,
        name="No artists",
        description="",
        scopes=["organization.read"],
        created_by=owner,
    )
    from django.test import Client

    api = Client()
    response = api.get(
        reverse("developer-artist-list"), HTTP_AUTHORIZATION=f"Bearer {allowed.secret}"
    )
    assert response.status_code == 200
    assert [item["stage_name"] for item in response.json()] == ["Signal North"]
    assert (
        api.get(
            reverse("developer-artist-list"),
            HTTP_AUTHORIZATION=f"Bearer {denied.secret}",
        ).status_code
        == 403
    )


def test_admin_deletion_disabled_and_relationship_validation(
    organization, other_organization, owner
):
    artist = Artist.objects.create(organization=organization, **artist_data())
    cross_membership = Membership.objects.create(
        user=User.objects.create_user(
            email="admin-cross@example.com", password=TEST_PASSWORD
        ),
        organization=other_organization,
    )
    assignment = ArtistTeamAssignment(artist=artist, membership=cross_membership)
    with pytest.raises(ValidationError):
        assignment.full_clean()
    request = type("Request", (), {"user": owner})()
    assert not ArtistAdmin(Artist, admin.site).has_delete_permission(request)
    assert not ArtistTeamAssignmentAdmin(
        ArtistTeamAssignment, admin.site
    ).has_delete_permission(request)
    assert not ArtistPortalLinkAdmin(
        ArtistPortalLink, admin.site
    ).has_delete_permission(request)


def test_removed_assignment_and_portal_link_can_be_safely_reactivated(
    owner, artist_user, organization
):
    artist = Artist.objects.create(organization=organization, **artist_data())
    membership = Membership.objects.get(user=owner, organization=organization)
    assignment = ArtistTeamAssignment.objects.create(
        artist=artist, membership=membership, responsibility="general", is_active=False
    )
    restored = assign_team_member(
        actor=owner,
        artist=artist,
        membership=membership,
        data={"responsibility": "manager", "is_primary": True},
    )
    assert restored.pk == assignment.pk and restored.is_active and restored.is_primary

    link = ArtistPortalLink.objects.create(
        artist=artist, user=artist_user, is_active=False
    )
    restored_link = link_portal_user(
        actor=owner,
        artist=artist,
        user=artist_user,
        relationship="artist",
    )
    assert restored_link.pk == link.pk and restored_link.is_active


def test_inactive_existing_membership_cannot_be_reassigned(owner, organization):
    artist = Artist.objects.create(organization=organization, **artist_data())
    membership = Membership.objects.create(
        user=User.objects.create_user(
            email="later-inactive@example.com", password=TEST_PASSWORD
        ),
        organization=organization,
        role=Membership.Role.MEMBER,
    )
    ArtistTeamAssignment.objects.create(
        artist=artist, membership=membership, responsibility="manager", is_active=False
    )
    membership.is_active = False
    membership.save(update_fields=("is_active", "updated_at"))
    with pytest.raises(ValidationError):
        assign_team_member(
            actor=owner,
            artist=artist,
            membership=membership,
            data={"responsibility": "manager"},
        )
