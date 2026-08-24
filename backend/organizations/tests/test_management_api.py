import pytest
from django.db import IntegrityError
from django.urls import reverse

from audit.models import AuditEvent
from organizations.models import Invitation, Membership
from organizations.services import create_invitation
from users.models import User

pytestmark = pytest.mark.django_db


def test_organization_list_and_retrieve_are_scoped(
    client, member, organization, other_organization
):
    client.force_login(member)
    response = client.get(reverse("organizations_api:organization-list"))
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(organization.id)]
    response = client.get(
        reverse(
            "organizations_api:organization-detail",
            kwargs={"organization_id": other_organization.id},
        )
    )
    assert response.status_code == 404


def test_owner_updates_organization_and_creates_audit(client, owner, organization):
    client.force_login(owner)
    response = client.patch(
        reverse(
            "organizations_api:organization-detail",
            kwargs={"organization_id": organization.id},
        ),
        {"name": "Updated Organization"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Organization"
    assert AuditEvent.objects.filter(action="organization.updated", actor=owner).exists()


def test_ordinary_member_cannot_update_organization(client, member, organization):
    client.force_login(member)
    response = client.patch(
        reverse(
            "organizations_api:organization-detail",
            kwargs={"organization_id": organization.id},
        ),
        {"name": "Denied"},
        content_type="application/json",
    )
    assert response.status_code == 403


def test_team_list_role_change_and_last_owner_protection(client, owner, member, organization):
    client.force_login(owner)
    list_url = reverse("organizations_api:member-list", kwargs={"organization_id": organization.id})
    assert client.get(list_url).status_code == 200
    member_membership = member.memberships.get(organization=organization)
    detail_url = reverse(
        "organizations_api:member-detail",
        kwargs={"organization_id": organization.id, "membership_id": member_membership.id},
    )
    response = client.patch(detail_url, {"role": "manager"}, content_type="application/json")
    assert response.status_code == 200
    assert response.json()["role"] == "manager"
    owner_membership = owner.memberships.get(organization=organization)
    owner_url = reverse(
        "organizations_api:member-detail",
        kwargs={"organization_id": organization.id, "membership_id": owner_membership.id},
    )
    response = client.patch(owner_url, {"is_active": False}, content_type="application/json")
    assert response.status_code == 400


@pytest.mark.parametrize("change", [{"role": "admin"}, {"is_active": False}])
def test_ineffective_owner_does_not_bypass_last_owner_protection(
    client, owner, organization, change
):
    inactive_user = User.objects.create_user(
        email="inactive-owner@example.com", password="Correct-Horse-123", is_active=False
    )
    Membership.objects.create(
        user=inactive_user,
        organization=organization,
        role=Membership.Role.OWNER,
        is_active=True,
    )
    inactive_membership_user = User.objects.create_user(
        email="inactive-membership-owner@example.com", password="Correct-Horse-123"
    )
    Membership.objects.create(
        user=inactive_membership_user,
        organization=organization,
        role=Membership.Role.OWNER,
        is_active=False,
    )
    owner_membership = owner.memberships.get(organization=organization)
    client.force_login(owner)
    response = client.patch(
        reverse(
            "organizations_api:member-detail",
            kwargs={
                "organization_id": organization.id,
                "membership_id": owner_membership.id,
            },
        ),
        change,
        content_type="application/json",
    )
    assert response.status_code == 400


def test_owner_change_is_allowed_with_another_effective_owner(client, owner, organization):
    other_owner = User.objects.create_user(
        email="other-owner@example.com", password="Correct-Horse-123"
    )
    Membership.objects.create(
        user=other_owner,
        organization=organization,
        role=Membership.Role.OWNER,
        is_active=True,
    )
    owner_membership = owner.memberships.get(organization=organization)
    client.force_login(owner)
    response = client.patch(
        reverse(
            "organizations_api:member-detail",
            kwargs={
                "organization_id": organization.id,
                "membership_id": owner_membership.id,
            },
        ),
        {"role": "admin"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_non_owner_membership_mutation_still_works(client, owner, member, organization):
    membership = member.memberships.get(organization=organization)
    client.force_login(owner)
    response = client.patch(
        reverse(
            "organizations_api:member-detail",
            kwargs={
                "organization_id": organization.id,
                "membership_id": membership.id,
            },
        ),
        {"is_active": False},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_invitation_create_list_revoke_and_cross_org_denial(
    client, owner, member, organization, other_organization
):
    client.force_login(owner)
    url = reverse("organizations_api:invitation-list", kwargs={"organization_id": organization.id})
    response = client.post(
        url,
        {"email": "new@example.com", "role": "member"},
        content_type="application/json",
    )
    assert response.status_code == 201
    assert "token" in response.json()
    invitation = Invitation.objects.get(pk=response.json()["id"])
    assert response.json()["token"] not in invitation.token_digest
    assert client.get(url).status_code == 200
    revoke_url = reverse(
        "organizations_api:invitation-revoke",
        kwargs={"invitation_id": invitation.id},
    )
    assert client.post(revoke_url).status_code == 200
    client.force_login(member)
    denied = reverse(
        "organizations_api:invitation-list",
        kwargs={"organization_id": other_organization.id},
    )
    assert client.get(denied).status_code == 404


def create_pending_invitation(organization, owner, email="pending@example.com"):
    return create_invitation(
        organization=organization,
        email=email,
        role=Membership.Role.MEMBER,
        invited_by=owner,
    ).invitation


@pytest.mark.parametrize(
    "role", [Membership.Role.MANAGER, Membership.Role.MEMBER, Membership.Role.ARTIST]
)
def test_roles_without_membership_manage_cannot_revoke_invitation(
    client, owner, organization, role
):
    invitation = create_pending_invitation(organization, owner)
    user = User.objects.create_user(email=f"{role}@example.com", password="Correct-Horse-123")
    Membership.objects.create(user=user, organization=organization, role=role)
    client.force_login(user)
    response = client.post(
        reverse(
            "organizations_api:invitation-revoke",
            kwargs={"invitation_id": invitation.id},
        )
    )
    assert response.status_code == 403
    invitation.refresh_from_db()
    assert invitation.revoked_at is None
    assert not AuditEvent.objects.filter(
        action="invitation.revoked", resource_id=str(invitation.id)
    ).exists()


@pytest.mark.parametrize("role", [Membership.Role.OWNER, Membership.Role.ADMIN])
def test_roles_with_membership_manage_can_revoke_invitation(client, owner, organization, role):
    invitation = create_pending_invitation(organization, owner, email=f"{role}@invite.test")
    actor = owner
    if role == Membership.Role.ADMIN:
        actor = User.objects.create_user(
            email="admin-revoker@example.com", password="Correct-Horse-123"
        )
        Membership.objects.create(user=actor, organization=organization, role=role)
    client.force_login(actor)
    response = client.post(
        reverse(
            "organizations_api:invitation-revoke",
            kwargs={"invitation_id": invitation.id},
        )
    )
    assert response.status_code == 200
    invitation.refresh_from_db()
    assert invitation.revoked_at is not None
    event = AuditEvent.objects.get(action="invitation.revoked", resource_id=str(invitation.id))
    assert event.actor == actor
    assert "token" not in event.description.lower()


def test_platform_superuser_can_revoke_invitation_cross_organization(
    client, superuser, owner, organization
):
    invitation = create_pending_invitation(organization, owner)
    client.force_login(superuser)
    response = client.post(
        reverse(
            "organizations_api:invitation-revoke",
            kwargs={"invitation_id": invitation.id},
        )
    )
    assert response.status_code == 200


def test_staff_without_organization_permission_cannot_revoke_invitation(
    client, owner, organization
):
    invitation = create_pending_invitation(organization, owner)
    staff = User.objects.create_user(
        email="staff-revoker@example.com",
        password="Correct-Horse-123",
        is_staff=True,
    )
    client.force_login(staff)
    response = client.post(
        reverse(
            "organizations_api:invitation-revoke",
            kwargs={"invitation_id": invitation.id},
        )
    )
    assert response.status_code == 403
    invitation.refresh_from_db()
    assert invitation.revoked_at is None


def test_member_cannot_create_invitation_through_api(client, member, organization):
    client.force_login(member)
    response = client.post(
        reverse(
            "organizations_api:invitation-list",
            kwargs={"organization_id": organization.id},
        ),
        {"email": "denied@example.com", "role": Membership.Role.MEMBER},
        content_type="application/json",
    )
    assert response.status_code == 403


def test_profile_is_safe_and_updates_only_names(client, user):
    client.force_login(user)
    url = reverse("organizations_api:profile")
    response = client.patch(
        url,
        {"first_name": "Taylor", "email": "changed@example.com", "is_superuser": True},
        content_type="application/json",
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.first_name == "Taylor"
    assert user.email == "member@example.com"
    assert not user.is_superuser
    assert "password" not in str(response.json()).lower()


def test_platform_endpoints_require_superuser(client, organization):
    staff = User.objects.create_user(
        email="staff-platform@example.com", password="Correct-Horse-123", is_staff=True
    )
    urls = [
        reverse("organizations_api:platform-overview"),
        reverse("organizations_api:platform-organizations"),
        reverse("organizations_api:platform-users"),
        reverse("platform-audit"),
    ]
    client.force_login(staff)
    assert all(client.get(url).status_code == 403 for url in urls)


def test_superuser_platform_lists_and_user_deactivation_are_audited(
    client, superuser, user, organization
):
    client.force_login(superuser)
    organizations = client.get(reverse("organizations_api:platform-organizations"))
    users = client.get(reverse("organizations_api:platform-users"))
    audit = client.get(reverse("platform-audit"))
    assert organizations.status_code == users.status_code == audit.status_code == 200
    detail = reverse("organizations_api:platform-user-detail", kwargs={"user_id": user.id})
    response = client.patch(detail, {"is_active": False}, content_type="application/json")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert AuditEvent.objects.filter(action="user.updated", actor=superuser).exists()


def test_superuser_cannot_deactivate_last_effective_owner(client, superuser, owner, organization):
    client.force_login(superuser)
    detail = reverse("organizations_api:platform-user-detail", kwargs={"user_id": owner.id})
    response = client.patch(detail, {"is_active": False}, content_type="application/json")
    assert response.status_code == 400
    owner.refresh_from_db()
    assert owner.is_active


def test_membership_uniqueness_remains_enforced(user, organization):
    Membership.objects.create(user=user, organization=organization)
    with pytest.raises(IntegrityError):
        Membership.objects.create(user=user, organization=organization)
