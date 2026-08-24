import uuid

import pytest
from django.core.exceptions import ValidationError

from users.models import User

pytestmark = pytest.mark.django_db


def test_user_email_is_normalized():
    user = User.objects.create_user(email="  PERSON@EXAMPLE.COM  ", password="Correct-Horse-123")
    assert user.email == "person@example.com"


def test_user_email_is_unique():
    User.objects.create_user(email="person@example.com", password="Correct-Horse-123")
    with pytest.raises(ValidationError):
        User.objects.create_user(email="PERSON@example.com", password="Correct-Horse-123")


def test_user_has_uuid_primary_key_and_hashed_password(user):
    assert isinstance(user.pk, uuid.UUID)
    assert user.check_password("Correct-Horse-123")
    assert user.password != "Correct-Horse-123"


def test_superuser_flags_are_validated():
    user = User.objects.create_superuser(email="admin@example.com", password="Correct-Horse-123")
    assert user.is_staff and user.is_superuser and user.is_active
    with pytest.raises(ValueError, match="is_staff"):
        User.objects.create_superuser(
            email="invalid@example.com", password="Correct-Horse-123", is_staff=False
        )
