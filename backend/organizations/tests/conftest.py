import pytest

from organizations.models import Membership, Organization
from users.models import User


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Nasty CSA", slug="nasty-csa")


@pytest.fixture
def other_organization(db):
    return Organization.objects.create(name="Other Org", slug="other-org")


@pytest.fixture
def owner(db, organization):
    user = User.objects.create_user(email="owner@example.com", password="Correct-Horse-123")
    Membership.objects.create(
        user=user, organization=organization, role=Membership.Role.OWNER, is_active=True
    )
    return user


@pytest.fixture
def member(db, organization):
    user = User.objects.create_user(email="member@example.com", password="Correct-Horse-123")
    Membership.objects.create(
        user=user, organization=organization, role=Membership.Role.MEMBER, is_active=True
    )
    return user
