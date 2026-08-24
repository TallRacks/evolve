import pytest

from organizations.models import Membership, Organization
from users.models import User


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="White Label Org", slug="white-label-org")


@pytest.fixture
def other_organization(db):
    return Organization.objects.create(name="Other White Label Org", slug="other-white-label-org")


@pytest.fixture
def owner(db, organization):
    user = User.objects.create_user(email="wl-owner@example.com", password="Correct-Horse-123")
    Membership.objects.create(user=user, organization=organization, role=Membership.Role.OWNER)
    return user


@pytest.fixture
def admin_user(db, organization):
    user = User.objects.create_user(email="wl-admin@example.com", password="Correct-Horse-123")
    Membership.objects.create(user=user, organization=organization, role=Membership.Role.ADMIN)
    return user


@pytest.fixture
def member(db, organization):
    user = User.objects.create_user(email="wl-member@example.com", password="Correct-Horse-123")
    Membership.objects.create(user=user, organization=organization, role=Membership.Role.MEMBER)
    return user
