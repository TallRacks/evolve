from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from organizations.models import Invitation, Membership
from organizations.services import (
    INVITATION_LIFETIME,
    accept_invitation,
    create_invitation,
    revoke_invitation,
)
from users.models import User

pytestmark = pytest.mark.django_db


def test_invitation_token_is_returned_once_and_only_digest_is_stored(owner, organization):
    now = timezone.now()
    with patch("organizations.services.timezone.now", return_value=now):
        created = create_invitation(
            organization=organization,
            email="INVITEE@example.com",
            role=Membership.Role.MEMBER,
            invited_by=owner,
        )
    assert len(created.token) >= 32
    assert created.token not in created.invitation.token_digest
    assert len(created.invitation.token_digest) == 64
    assert created.invitation.expires_at == now + INVITATION_LIFETIME
    assert created.invitation.expires_at - now == timedelta(days=7)


def test_valid_invitation_can_be_accepted_once(owner, organization):
    created = create_invitation(
        organization=organization,
        email="invitee@example.com",
        role=Membership.Role.MANAGER,
        invited_by=owner,
    )
    invitee = User.objects.create_user(email="invitee@example.com", password="Correct-Horse-123")
    membership = accept_invitation(token=created.token, user=invitee)
    assert membership.role == Membership.Role.MANAGER
    assert membership.is_active
    with pytest.raises(ValidationError, match="already been accepted"):
        accept_invitation(token=created.token, user=invitee)


def test_expired_and_revoked_invitations_are_rejected(owner, organization):
    expired = create_invitation(
        organization=organization,
        email="expired@example.com",
        role=Membership.Role.MEMBER,
        invited_by=owner,
    )
    Invitation.objects.filter(pk=expired.invitation.pk).update(expires_at=timezone.now())
    expired_user = User.objects.create_user(
        email="expired@example.com", password="Correct-Horse-123"
    )
    with pytest.raises(ValidationError, match="expired"):
        accept_invitation(token=expired.token, user=expired_user)

    revoked = create_invitation(
        organization=organization,
        email="revoked@example.com",
        role=Membership.Role.MEMBER,
        invited_by=owner,
    )
    revoke_invitation(invitation=revoked.invitation, revoked_by=owner)
    revoked_user = User.objects.create_user(
        email="revoked@example.com", password="Correct-Horse-123"
    )
    with pytest.raises(ValidationError, match="revoked"):
        accept_invitation(token=revoked.token, user=revoked_user)


def test_invitation_email_must_match_user(owner, organization):
    created = create_invitation(
        organization=organization,
        email="intended@example.com",
        role=Membership.Role.MEMBER,
        invited_by=owner,
    )
    other = User.objects.create_user(email="other@example.com", password="Correct-Horse-123")
    with pytest.raises(ValidationError, match="does not match"):
        accept_invitation(token=created.token, user=other)


def test_duplicate_outstanding_invitation_revokes_previous(owner, organization):
    first = create_invitation(
        organization=organization,
        email="invitee@example.com",
        role=Membership.Role.MEMBER,
        invited_by=owner,
    )
    second = create_invitation(
        organization=organization,
        email="invitee@example.com",
        role=Membership.Role.ADMIN,
        invited_by=owner,
    )
    first.invitation.refresh_from_db()
    assert first.invitation.revoked_at is not None
    assert second.invitation.revoked_at is None


def test_user_without_permission_cannot_invite(member, organization):
    with pytest.raises(PermissionDenied):
        create_invitation(
            organization=organization,
            email="invitee@example.com",
            role=Membership.Role.MEMBER,
            invited_by=member,
        )
