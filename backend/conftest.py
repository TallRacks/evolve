import pytest

from users.models import User


@pytest.fixture
def user(db):
    return User.objects.create_user(email="member@example.com", password="Correct-Horse-123")


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(email="root@example.com", password="Correct-Horse-123")
