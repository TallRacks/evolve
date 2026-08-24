from datetime import date, timedelta

import pytest
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from artists.models import Artist, ArtistPortalLink
from audit.models import AuditEvent
from campaigns.admin import CampaignAdmin
from campaigns.models import (
    Campaign,
    CampaignChannel,
    Rollout,
    RolloutTask,
)
from campaigns.services import (
    add_dependency,
    complete_task,
    create_campaign,
    create_milestone,
    create_rollout,
    create_task,
    transition_campaign,
    transition_rollout,
    transition_task,
)
from music.models import Release
from notifications.models import NotificationRecipient
from organizations.models import Membership, Organization
from users.models import User
from white_label.services import create_api_client_key

pytestmark = pytest.mark.django_db
PASSWORD = "Test-only-campaign-credential-123"


@pytest.fixture
def org():
    return Organization.objects.create(name="Campaign Org", slug="campaign-org")


@pytest.fixture
def other():
    return Organization.objects.create(name="Other Campaign", slug="other-campaign")


def member(org, role, email):
    user = User.objects.create_user(email=email, password=PASSWORD)
    membership = Membership.objects.create(user=user, organization=org, role=role)
    return user, membership


@pytest.fixture
def owner(org):
    return member(org, Membership.Role.OWNER, "campaign-owner@example.invalid")


@pytest.fixture
def artist(org):
    return Artist.objects.create(
        organization=org, stage_name="Campaign Artist", slug="campaign-artist"
    )


@pytest.fixture
def release(org, artist):
    return Release.objects.create(
        organization=org,
        primary_artist=artist,
        title="Linked Release",
        slug="linked-release",
        release_type=Release.Type.SINGLE,
    )


@pytest.fixture
def campaign(owner, org, artist, release):
    return create_campaign(
        actor=owner[0],
        organization=org,
        data={
            "artist": artist,
            "release": release,
            "name": "Launch Campaign",
            "slug": "launch-campaign",
            "objective": Campaign.Objective.RELEASE_LAUNCH,
            "start_date": date(2027, 1, 1),
            "end_date": date(2027, 2, 1),
            "owner_membership": owner[1],
        },
    )


@pytest.fixture
def rollout(owner, campaign):
    return create_rollout(
        actor=owner[0],
        campaign=campaign,
        data={"name": "Main Rollout", "owner_membership": owner[1]},
    )


def test_campaign_create_uuid_relationship_dates_audit(campaign):
    assert campaign.id and campaign.status == Campaign.Status.DRAFT
    assert AuditEvent.objects.filter(
        action="campaign.created", resource_id=str(campaign.id)
    ).exists()
    campaign.start_date = date(2028, 1, 2)
    campaign.end_date = date(2028, 1, 1)
    with pytest.raises(ValidationError):
        campaign.save()


def test_campaign_relationship_and_owner_isolation(owner, org, other, artist):
    other_artist = Artist.objects.create(organization=other, stage_name="Other", slug="other")
    _, other_membership = member(other, Membership.Role.MANAGER, "other-owner@example.invalid")
    for data in (
        {"artist": other_artist},
        {"artist": artist, "owner_membership": other_membership},
    ):
        with pytest.raises(ValidationError):
            create_campaign(
                actor=owner[0],
                organization=org,
                data={
                    **data,
                    "name": "Invalid",
                    "slug": "invalid-" + str(len(data)),
                    "objective": "other",
                },
            )


def test_campaign_lifecycle_and_direct_bypass(owner, campaign):
    campaign.status = Campaign.Status.ACTIVE
    with pytest.raises(ValidationError):
        campaign.save()
    campaign.refresh_from_db()
    campaign = transition_campaign(
        actor=owner[0], campaign=campaign, to_status=Campaign.Status.PLANNED
    )
    campaign = transition_campaign(
        actor=owner[0], campaign=campaign, to_status=Campaign.Status.ACTIVE
    )
    campaign = transition_campaign(
        actor=owner[0], campaign=campaign, to_status=Campaign.Status.COMPLETED
    )
    campaign = transition_campaign(
        actor=owner[0], campaign=campaign, to_status=Campaign.Status.ARCHIVED
    )
    assert campaign.status == Campaign.Status.ARCHIVED
    with pytest.raises(ValidationError):
        campaign.delete()


def test_channel_constraints(campaign):
    CampaignChannel.objects.create(campaign=campaign, channel="instagram", is_primary=True)
    with pytest.raises(ValidationError):
        duplicate = CampaignChannel(campaign=campaign, channel="instagram")
        duplicate.full_clean()


def test_rollout_lifecycle_progress_and_audit(owner, rollout):
    first = create_task(actor=owner[0], rollout=rollout, data={"title": "First"})
    create_task(actor=owner[0], rollout=rollout, data={"title": "Cancelled"})
    complete_task(actor=owner[0], task=first)
    cancelled = rollout.tasks.exclude(pk=first.pk).get()
    transition_task(actor=owner[0], task=cancelled, to_status=RolloutTask.Status.CANCELLED)
    assert rollout.progress == 100
    rollout = transition_rollout(actor=owner[0], rollout=rollout, to_status=Rollout.Status.ACTIVE)
    assert rollout.status == Rollout.Status.ACTIVE
    assert AuditEvent.objects.filter(action="rollout.task_completed").exists()


def test_milestone_order_and_active_owner(owner, rollout, org):
    milestone = create_milestone(
        actor=owner[0],
        rollout=rollout,
        data={"title": "Announcement", "sequence": 2, "owner_membership": owner[1]},
    )
    assert milestone.sequence == 2
    inactive_user, inactive = member(org, Membership.Role.MEMBER, "inactive-member@example.invalid")
    inactive.is_active = False
    inactive.save()
    with pytest.raises(ValidationError):
        create_milestone(
            actor=owner[0],
            rollout=rollout,
            data={"title": "Invalid", "sequence": 3, "owner_membership": inactive},
        )


def test_task_completion_reopen_overdue_and_assignment(owner, rollout, other):
    manager = member(
        rollout.organization, Membership.Role.MANAGER, "task-manager@example.invalid"
    )
    task = create_task(
        actor=owner[0],
        rollout=rollout,
        data={
            "title": "Due",
            "assigned_membership": manager[1],
            "due_date": timezone.localdate() - timedelta(days=1),
        },
    )
    assert task.is_overdue
    assert NotificationRecipient.objects.filter(
        user=manager[0], notification__notification_type="rollout.task_assigned"
    ).exists()
    task = complete_task(actor=manager[0], task=task)
    assert NotificationRecipient.objects.filter(
        user=owner[0], notification__notification_type="rollout.task_completed"
    ).exists()
    assert task.completed_at and task.completed_by == manager[0] and not task.is_overdue
    task = transition_task(actor=owner[0], task=task, to_status=RolloutTask.Status.TODO)
    assert task.completed_at is None
    _, wrong = member(other, Membership.Role.MEMBER, "wrong-task@example.invalid")
    with pytest.raises(ValidationError):
        create_task(
            actor=owner[0], rollout=rollout, data={"title": "Wrong", "assigned_membership": wrong}
        )


def test_dependencies_duplicate_self_cross_and_cycles(owner, rollout, org, artist):
    a = create_task(actor=owner[0], rollout=rollout, data={"title": "A"})
    b = create_task(actor=owner[0], rollout=rollout, data={"title": "B"})
    c = create_task(actor=owner[0], rollout=rollout, data={"title": "C"})
    add_dependency(actor=owner[0], task=b, depends_on=a)
    add_dependency(actor=owner[0], task=c, depends_on=b)
    with pytest.raises(ValidationError):
        add_dependency(actor=owner[0], task=a, depends_on=c)
    with pytest.raises(ValidationError):
        add_dependency(actor=owner[0], task=a, depends_on=a)
    with pytest.raises(ValidationError):
        add_dependency(actor=owner[0], task=b, depends_on=a)
    other_campaign = create_campaign(
        actor=owner[0],
        organization=org,
        data={"artist": artist, "name": "Other", "slug": "other-plan", "objective": "other"},
    )
    other_rollout = create_rollout(actor=owner[0], campaign=other_campaign, data={"name": "Other"})
    outside = create_task(actor=owner[0], rollout=other_rollout, data={"title": "Outside"})
    with pytest.raises(ValidationError):
        add_dependency(actor=owner[0], task=a, depends_on=outside)


def test_permissions_staff_no_bypass_and_superuser(owner, campaign, org):
    member_user, _ = member(org, Membership.Role.MEMBER, "campaign-member@example.invalid")
    with pytest.raises(PermissionDenied):
        transition_campaign(actor=member_user, campaign=campaign, to_status=Campaign.Status.PLANNED)
    staff = User.objects.create_user(
        email="campaign-staff@example.invalid", password=PASSWORD, is_staff=True
    )
    with pytest.raises(PermissionDenied):
        transition_campaign(actor=staff, campaign=campaign, to_status=Campaign.Status.PLANNED)
    root = User.objects.create_superuser(email="campaign-root@example.invalid", password=PASSWORD)
    assert transition_campaign(actor=root, campaign=campaign, to_status=Campaign.Status.PLANNED)


def test_artist_portal_isolation(client, owner, org, artist, campaign):
    portal, _ = member(org, Membership.Role.ARTIST, "campaign-portal@example.invalid")
    ArtistPortalLink.objects.create(artist=artist, user=portal)
    hidden = Artist.objects.create(organization=org, stage_name="Hidden", slug="hidden-campaign")
    create_campaign(
        actor=owner[0],
        organization=org,
        data={"artist": hidden, "name": "Hidden", "slug": "hidden", "objective": "other"},
    )
    transition_campaign(actor=owner[0], campaign=campaign, to_status=Campaign.Status.PLANNED)
    client.force_login(portal)
    data = client.get("/api/artist-portal/campaigns/").json()
    assert [x["id"] for x in data] == [str(campaign.id)]
    assert "summary" not in data[0]
    assert "owner" not in data[0]


def test_developer_scope_and_privacy(client, owner, org, campaign, rollout):
    _, created = create_api_client_key(
        organization=org,
        name="Campaign API",
        description="",
        scopes=["campaign.read"],
        created_by=owner[0],
    )
    headers = {"HTTP_AUTHORIZATION": f"Bearer {created.secret}"}
    response = client.get("/api/developer/campaigns/", **headers)
    assert response.status_code == 200 and response.json()[0]["id"] == str(campaign.id)
    assert "summary" not in response.json()[0]
    _, denied = create_api_client_key(
        organization=org,
        name="Denied",
        description="",
        scopes=["organization.read"],
        created_by=owner[0],
    )
    assert (
        client.get(
            "/api/developer/rollouts/", HTTP_AUTHORIZATION=f"Bearer {denied.secret}"
        ).status_code
        == 403
    )


def test_api_crud_and_status(client, owner, org, artist):
    client.force_login(owner[0])
    created = client.post(
        "/api/campaigns/",
        {
            "organization_id": str(org.id),
            "artist_id": str(artist.id),
            "name": "API Campaign",
            "slug": "api-campaign",
            "objective": "awareness",
        },
        content_type="application/json",
    )
    assert created.status_code == 201
    cid = created.json()["id"]
    assert (
        client.patch(
            f"/api/campaigns/{cid}/", {"status": "active"}, content_type="application/json"
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/api/campaigns/{cid}/status/",
            {"to_status": "planned"},
            content_type="application/json",
        ).status_code
        == 200
    )
    ro = client.post(
        f"/api/campaigns/{cid}/rollouts/", {"name": "API rollout"}, content_type="application/json"
    )
    assert ro.status_code == 201
    task = client.post(
        f"/api/rollouts/{ro.json()['id']}/tasks/",
        {"title": "API Task"},
        content_type="application/json",
    )
    assert task.status_code == 201
    assert (
        client.post(
            f"/api/rollout-tasks/{task.json()['id']}/complete/", {}, content_type="application/json"
        ).status_code
        == 200
    )


def test_admin_status_and_delete_safeguards(owner, campaign):
    model_admin = CampaignAdmin(Campaign, admin.site)
    assert model_admin.has_delete_permission(type("R", (), {"user": owner[0]})(), campaign) is False
    campaign.status = Campaign.Status.ACTIVE
    with pytest.raises(ValidationError):
        campaign.save()
