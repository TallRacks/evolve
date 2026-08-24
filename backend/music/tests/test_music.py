from datetime import date

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import RequestFactory

from artists.models import Artist, ArtistPortalLink
from audit.models import AuditEvent
from contacts.models import Contact
from music.admin import ReleaseAdmin
from music.models import MusicCredit, Release, ReleaseLink, Track
from music.services import (
    add_release_track,
    create_credit,
    create_release,
    create_track,
    transition_release,
    update_release,
)
from organizations.models import Membership, Organization
from users.models import User
from white_label.services import create_api_client_key

pytestmark = pytest.mark.django_db
PASSWORD = "Test-only-music-credential-123"


@pytest.fixture
def organization():
    return Organization.objects.create(name="Music Org", slug="music-org")


@pytest.fixture
def other_organization():
    return Organization.objects.create(name="Other Music", slug="other-music")


def user_for(organization, role, email):
    user = User.objects.create_user(email=email, password=PASSWORD)
    Membership.objects.create(user=user, organization=organization, role=role)
    return user


@pytest.fixture
def owner(organization):
    return user_for(organization, Membership.Role.OWNER, "music-owner@example.invalid")


@pytest.fixture
def artist(organization):
    return Artist.objects.create(
        organization=organization, stage_name="Catalog Artist", slug="catalog-artist"
    )


@pytest.fixture
def release(owner, organization, artist):
    return create_release(
        actor=owner,
        organization=organization,
        data={
            "primary_artist": artist,
            "title": "First Release",
            "slug": "first-release",
            "release_type": Release.Type.SINGLE,
            "planned_release_date": date(2027, 1, 2),
        },
    )


@pytest.fixture
def track(owner, organization, artist):
    return create_track(
        actor=owner,
        organization=organization,
        data={
            "primary_artist": artist,
            "title": "First Track",
            "version_title": "Radio Edit",
            "slug": "first-track-radio",
            "isrc": "za-abc-26-12345",
        },
    )


def test_release_create_uuid_slug_scope_and_audit(release):
    assert release.id
    assert release.status == Release.Status.DRAFT
    assert AuditEvent.objects.filter(action="release.created", resource_id=str(release.id)).exists()
    with pytest.raises(ValidationError):
        Release.objects.create(
            organization=release.organization,
            primary_artist=release.primary_artist,
            title="Duplicate",
            slug=release.slug,
            release_type=Release.Type.EP,
        )


def test_release_lifecycle_and_generic_status_rejected(owner, release):
    with pytest.raises(ValidationError):
        update_release(actor=owner, release=release, data={"status": Release.Status.RELEASED})
    with pytest.raises(ValidationError):
        transition_release(actor=owner, release=release, to_status=Release.Status.RELEASED)
    release = transition_release(actor=owner, release=release, to_status=Release.Status.SCHEDULED)
    release = transition_release(actor=owner, release=release, to_status=Release.Status.RELEASED)
    release = transition_release(actor=owner, release=release, to_status=Release.Status.ARCHIVED)
    assert release.status == Release.Status.ARCHIVED
    assert AuditEvent.objects.filter(action="release.archived").exists()


def test_track_isrc_normalization_global_uniqueness_and_version(owner, organization, artist, track):
    assert track.isrc == "ZAABC2612345"
    assert track.version_title == "Radio Edit"
    with pytest.raises(ValidationError):
        create_track(
            actor=owner,
            organization=organization,
            data={
                "primary_artist": artist,
                "title": "Duplicate ISRC",
                "slug": "duplicate-isrc",
                "isrc": "ZAABC2612345",
            },
        )


def test_cross_organization_artist_and_track_rejected(
    owner, organization, artist, release, other_organization
):
    other_artist = Artist.objects.create(
        organization=other_organization, stage_name="Other", slug="other"
    )
    with pytest.raises(ValidationError):
        create_track(
            actor=owner,
            organization=organization,
            data={"primary_artist": other_artist, "title": "Cross", "slug": "cross"},
        )
    other_track = Track(
        organization=other_organization,
        primary_artist=other_artist,
        title="Other Track",
        slug="other-track",
    )
    other_track.save()
    with pytest.raises(ValidationError):
        add_release_track(
            actor=owner,
            release=release,
            track=other_track,
            data={"track_number": 1, "sequence": 1},
        )


def test_release_track_order_and_uniqueness(owner, release, track):
    placement = add_release_track(
        actor=owner,
        release=release,
        track=track,
        data={"disc_number": 1, "track_number": 1, "sequence": 1, "is_focus_track": True},
    )
    assert placement.track == track
    with pytest.raises(ValidationError):
        add_release_track(
            actor=owner,
            release=release,
            track=track,
            data={"disc_number": 1, "track_number": 2, "sequence": 2},
        )
    second = Track.objects.create(
        organization=track.organization,
        primary_artist=track.primary_artist,
        title="Second",
        slug="second",
    )
    with pytest.raises(ValidationError):
        add_release_track(
            actor=owner,
            release=release,
            track=second,
            data={"disc_number": 1, "track_number": 1, "sequence": 2},
        )


def test_credit_requirement_external_and_same_org(owner, organization, release, other_organization):
    with pytest.raises(ValidationError):
        MusicCredit(organization=organization, name="Nobody", credit_role="producer").save()
    credit = create_credit(
        actor=owner,
        organization=organization,
        resource=release,
        data={"release": release, "name": "External Producer", "credit_role": "producer"},
    )
    assert credit.linked_artist is None
    other_contact = Contact.objects.create(
        organization=other_organization, first_name="Cross", last_name="Contact"
    )
    with pytest.raises(ValidationError):
        create_credit(
            actor=owner,
            organization=organization,
            resource=release,
            data={
                "release": release,
                "name": "Cross",
                "credit_role": "producer",
                "linked_contact": other_contact,
            },
        )


def test_member_read_manager_manage_staff_denied_and_superuser_cross_org(
    client, organization, artist, release
):
    member = user_for(organization, Membership.Role.MEMBER, "music-member@example.invalid")
    manager = user_for(organization, Membership.Role.MANAGER, "music-manager@example.invalid")
    client.force_login(member)
    assert client.get(f"/api/music/releases/?organization_id={organization.id}").status_code == 200
    denied = client.post(
        "/api/music/tracks/",
        {
            "organization_id": str(organization.id),
            "primary_artist_id": str(artist.id),
            "title": "Denied",
            "slug": "denied",
        },
        content_type="application/json",
    )
    assert denied.status_code == 403
    client.force_login(manager)
    assert (
        client.post(
            "/api/music/tracks/",
            {
                "organization_id": str(organization.id),
                "primary_artist_id": str(artist.id),
                "title": "Allowed",
                "slug": "allowed",
            },
            content_type="application/json",
        ).status_code
        == 201
    )
    staff = User.objects.create_user(
        email="music-staff@example.invalid", password=PASSWORD, is_staff=True
    )
    client.force_login(staff)
    assert client.get(f"/api/music/releases/{release.id}/").status_code == 404
    platform = User.objects.create_superuser(email="music-root@example.invalid", password=PASSWORD)
    client.force_login(platform)
    assert client.get(f"/api/platform/music/releases/{release.id}/").status_code == 200


def test_artist_portal_is_limited_to_linked_artist(client, organization, owner, artist, release):
    portal = user_for(organization, Membership.Role.ARTIST, "portal-music@example.invalid")
    ArtistPortalLink.objects.create(artist=artist, user=portal)
    other = Artist.objects.create(organization=organization, stage_name="Hidden", slug="hidden")
    create_release(
        actor=owner,
        organization=organization,
        data={
            "primary_artist": other,
            "title": "Hidden Release",
            "slug": "hidden-release",
            "release_type": Release.Type.ALBUM,
            "planned_release_date": date(2027, 2, 1),
        },
    )
    transition_release(actor=owner, release=release, to_status=Release.Status.SCHEDULED)
    client.force_login(portal)
    payload = client.get("/api/artist-portal/music/").json()
    assert [item["title"] for item in payload["releases"]] == ["First Release"]
    assert all("internal_notes" not in item for item in payload["releases"])


def test_developer_scope_org_isolation_and_privacy(
    client, owner, organization, release, track, other_organization
):
    _, key = create_api_client_key(
        organization=organization,
        name="Music",
        description="",
        scopes=["music.read"],
        created_by=owner,
    )
    response = client.get("/api/developer/releases/", HTTP_AUTHORIZATION=f"Bearer {key.secret}")
    assert response.status_code == 200
    assert response.json()[0]["title"] == release.title
    assert "internal_notes" not in response.json()[0]
    track_payload = client.get(
        "/api/developer/tracks/", HTTP_AUTHORIZATION=f"Bearer {key.secret}"
    ).json()[0]
    assert track_payload["isrc"] == track.isrc
    assert "internal_notes" not in track_payload
    _, missing = create_api_client_key(
        organization=other_organization,
        name="Missing",
        description="",
        scopes=["organization.read"],
        created_by=owner,
    )
    assert (
        client.get(
            "/api/developer/releases/", HTTP_AUTHORIZATION=f"Bearer {missing.secret}"
        ).status_code
        == 403
    )


def test_admin_status_and_delete_safeguards(owner, release):
    model_admin = ReleaseAdmin(Release, admin.site)
    request = RequestFactory().post("/admin/")
    request.user = owner
    assert model_admin.has_delete_permission(request, release) is False
    release.status = Release.Status.RELEASED
    with pytest.raises(ValidationError):
        release.save()


def test_links_use_constrained_platform_and_primary_uniqueness(release):
    first = ReleaseLink.objects.create(
        release=release,
        platform=ReleaseLink.Platform.SPOTIFY,
        url="https://example.invalid/spotify",
        is_primary=True,
    )
    assert first.is_primary
    with pytest.raises(IntegrityError), transaction.atomic():
        ReleaseLink.objects.create(
            release=release,
            platform=ReleaseLink.Platform.APPLE_MUSIC,
            url="https://example.invalid/apple",
            is_primary=True,
        )


@pytest.mark.django_db(transaction=True)
def test_concurrent_release_transitions_are_serialized_on_postgresql(organization, owner, artist):
    from concurrent.futures import ThreadPoolExecutor

    from django.db import connection, connections

    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock regression test")
    release = create_release(
        actor=owner,
        organization=organization,
        data={
            "primary_artist": artist,
            "title": "Concurrent Release",
            "slug": "concurrent-release",
            "release_type": Release.Type.SINGLE,
            "planned_release_date": date(2027, 2, 1),
        },
    )
    transition_release(actor=owner, release=release, to_status=Release.Status.SCHEDULED)

    def transition(to_status):
        connections.close_all()
        try:
            thread_actor = User.objects.get(pk=owner.pk)
            thread_release = Release.objects.get(pk=release.pk)
            transition_release(
                actor=thread_actor, release=thread_release, to_status=to_status
            )
            return "ok"
        except ValidationError:
            return "rejected"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(transition, [Release.Status.RELEASED, Release.Status.CANCELLED])
        )

    release.refresh_from_db()
    assert sorted(results) == ["ok", "rejected"]
    assert release.status in {Release.Status.RELEASED, Release.Status.CANCELLED}


def test_credit_partial_update_preserves_omitted_link(client, owner, organization, artist, release):
    contact = Contact.objects.create(
        organization=organization, first_name="Linked", last_name="Contributor"
    )
    credit = create_credit(
        actor=owner,
        organization=organization,
        resource=release,
        data={
            "release": release,
            "name": "Linked Contributor",
            "credit_role": "producer",
            "linked_contact": contact,
        },
    )
    client.force_login(owner)
    response = client.patch(
        f"/api/music/releases/{release.id}/credits/{credit.id}/",
        {"display_order": 2},
        content_type="application/json",
    )
    credit.refresh_from_db()
    assert response.status_code == 200
    assert credit.linked_contact == contact


def test_release_and_track_details_include_artist_display_fields(client, owner, release, track):
    client.force_login(owner)
    release_data = client.get(f"/api/music/releases/{release.id}/").json()
    track_data = client.get(f"/api/music/tracks/{track.id}/").json()
    assert release_data["artist"] == release.primary_artist.stage_name
    assert release_data["artist_id"] == str(release.primary_artist_id)
    assert track_data["artist"] == track.primary_artist.stage_name
    assert track_data["artist_id"] == str(track.primary_artist_id)
