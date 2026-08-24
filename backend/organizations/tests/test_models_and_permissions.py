import uuid

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError

from organizations.api.permissions import (
    ActiveOrganizationMember,
    ArtistAccess,
    PlatformSuperuser,
)
from organizations.models import Membership, Organization
from organizations.permissions import (
    permissions_for_role,
    user_has_organization_access,
    user_has_organization_permission,
)
from organizations.selectors import organizations_for_user
from users.models import User

pytestmark = pytest.mark.django_db


def test_organization_uses_uuid_and_unique_slug():
    organization = Organization.objects.create(name="One", slug="one")
    assert isinstance(organization.pk, uuid.UUID)
    with pytest.raises(IntegrityError):
        Organization.objects.create(name="Duplicate", slug="one")


def test_membership_is_unique_per_user_and_organization(user, organization):
    Membership.objects.create(user=user, organization=organization, role=Membership.Role.MEMBER)
    with pytest.raises(IntegrityError):
        Membership.objects.create(user=user, organization=organization, role=Membership.Role.ADMIN)


def test_only_active_membership_grants_access(user, organization):
    membership = Membership.objects.create(
        user=user, organization=organization, role=Membership.Role.MEMBER, is_active=False
    )
    assert not user_has_organization_access(user, organization)
    membership.is_active = True
    membership.save(update_fields=("is_active", "updated_at"))
    assert user_has_organization_access(user, organization)
    organization.is_active = False
    organization.save(update_fields=("is_active", "updated_at"))
    assert not user_has_organization_access(user, organization)


def test_role_permission_is_centralized(owner, member, organization):
    assert user_has_organization_permission(owner, organization, "membership.manage")
    assert not user_has_organization_permission(member, organization, "membership.manage")
    assert user_has_organization_permission(member, organization, "organization.view")
    assert permissions_for_role(Membership.Role.ARTIST) == [
        "organization.view",
        "portal.artist",
    ]


def test_superuser_crosses_organization_boundaries(superuser, organization, other_organization):
    assert user_has_organization_access(superuser, organization)
    assert user_has_organization_permission(superuser, other_organization, "membership.manage")
    assert set(organizations_for_user(superuser)) == {organization, other_organization}
    request = type("Request", (), {"user": superuser})()
    assert PlatformSuperuser().has_permission(request, None)


def test_staff_non_superuser_has_no_implicit_access(organization):
    staff = User.objects.create_user(
        email="staff@example.com", password="Correct-Horse-123", is_staff=True
    )
    assert not user_has_organization_access(staff, organization)
    assert not user_has_organization_permission(staff, organization, "organization.view")
    request = type("Request", (), {"user": staff})()
    assert not PlatformSuperuser().has_permission(request, None)


def test_normal_user_cannot_scope_by_organization_id_alone(member, other_organization):
    assert not user_has_organization_access(member, other_organization)
    assert not organizations_for_user(member).filter(pk=other_organization.pk).exists()
    assert not user_has_organization_access(AnonymousUser(), other_organization)


def test_artist_access_requires_artist_membership(user, organization):
    membership = Membership.objects.create(
        user=user, organization=organization, role=Membership.Role.MEMBER
    )
    request = type("Request", (), {"user": user})()
    view = type("View", (), {"organization": organization})()
    assert not ArtistAccess().has_permission(request, view)
    membership.role = Membership.Role.ARTIST
    membership.save(update_fields=("role", "updated_at"))
    assert ArtistAccess().has_permission(request, view)


def test_active_organization_permission_rechecks_membership(user, organization):
    membership = Membership.objects.create(user=user, organization=organization)
    request = type("Request", (), {"user": user})()
    permission = ActiveOrganizationMember()
    assert permission.has_object_permission(request, None, organization)
    membership.is_active = False
    membership.save(update_fields=("is_active", "updated_at"))
    assert not permission.has_object_permission(request, None, organization)
