import pytest

from organizations.models import Membership, Organization
from users.models import User

TEST_PASSWORD = "Correct-Horse-123"


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Artist Org", slug="artist-org")


@pytest.fixture
def other_organization(db):
    return Organization.objects.create(name="Other Artist Org", slug="other-artist-org")


@pytest.fixture
def owner(organization):
    user = User.objects.create_user(
        email="artist-owner@example.com", password=TEST_PASSWORD
    )
    Membership.objects.create(
        user=user, organization=organization, role=Membership.Role.OWNER
    )
    return user


@pytest.fixture
def manager(organization):
    user = User.objects.create_user(
        email="artist-manager@example.com", password=TEST_PASSWORD
    )
    Membership.objects.create(
        user=user, organization=organization, role=Membership.Role.MANAGER
    )
    return user


@pytest.fixture
def member(organization):
    user = User.objects.create_user(
        email="artist-member@example.com", password=TEST_PASSWORD
    )
    Membership.objects.create(
        user=user, organization=organization, role=Membership.Role.MEMBER
    )
    return user


@pytest.fixture
def artist_user(organization):
    user = User.objects.create_user(
        email="portal-artist@example.com", password=TEST_PASSWORD
    )
    Membership.objects.create(
        user=user, organization=organization, role=Membership.Role.ARTIST
    )
    return user


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        email="artist-platform@example.com", password=TEST_PASSWORD
    )
