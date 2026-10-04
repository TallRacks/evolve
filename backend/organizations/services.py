import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from users.managers import UserManager
from users.models import User

from .models import Invitation, Membership, Organization
from .permissions import user_has_organization_permission

INVITATION_LIFETIME = timedelta(days=7)


@dataclass(frozen=True)
class CreatedInvitation:
    invitation: Invitation
    token: str


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@transaction.atomic
def create_invitation(
    *, organization: Organization, email: str, role: str, invited_by
) -> CreatedInvitation:
    if not user_has_organization_permission(invited_by, organization, "membership.manage"):
        raise PermissionDenied("You cannot invite members to this organization")
    if role not in Membership.Role.values:
        raise ValidationError("Invalid membership role")
    normalized_email = UserManager.normalize_login_email(email)
    now = timezone.now()
    Invitation.objects.select_for_update().filter(
        organization=organization,
        email=normalized_email,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
        expires_at__gt=now,
    ).update(revoked_at=now)
    token = secrets.token_urlsafe(32)
    invitation = Invitation.objects.create(
        organization=organization,
        email=normalized_email,
        role=role,
        invited_by=invited_by,
        token_digest=_token_digest(token),
        expires_at=now + INVITATION_LIFETIME,
    )
    from notifications.email_delivery import schedule_invitation_email

    schedule_invitation_email(invitation, token)
    return CreatedInvitation(invitation=invitation, token=token)


@transaction.atomic
def accept_invitation(*, token: str, user) -> Membership:
    now = timezone.now()
    try:
        invitation = (
            Invitation.objects.select_for_update()
            .select_related("organization")
            .get(token_digest=_token_digest(token))
        )
    except Invitation.DoesNotExist as error:
        raise ValidationError("Invalid invitation") from error
    if invitation.accepted_at is not None:
        raise ValidationError("Invitation has already been accepted")
    if invitation.revoked_at is not None:
        raise ValidationError("Invitation has been revoked")
    if invitation.expires_at <= now:
        raise ValidationError("Invitation has expired")
    if not invitation.organization.is_active:
        raise ValidationError("Organization is inactive")
    if UserManager.normalize_login_email(user.email) != invitation.email:
        raise ValidationError("Invitation email does not match this user")
    membership, _ = Membership.objects.update_or_create(
        user=user,
        organization=invitation.organization,
        defaults={"role": invitation.role, "is_active": True},
    )
    invitation.accepted_at = now
    invitation.save(update_fields=("accepted_at", "updated_at"))
    return membership


@transaction.atomic
def revoke_invitation(*, invitation: Invitation, revoked_by) -> Invitation:
    invitation = Invitation.objects.select_for_update().get(pk=invitation.pk)
    if not user_has_organization_permission(
        revoked_by, invitation.organization, "membership.manage"
    ):
        raise PermissionDenied("You cannot revoke this invitation")
    if invitation.accepted_at is not None:
        raise ValidationError("Accepted invitations cannot be revoked")
    if invitation.revoked_at is None:
        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=("revoked_at", "updated_at"))
    return invitation


@transaction.atomic
def signup_invitation(*, token: str, full_name: str, password: str):
    now = timezone.now()
    try:
        invitation = (Invitation.objects.select_for_update().select_related("organization").get(token_digest=_token_digest(token)))
    except Invitation.DoesNotExist as error:
        raise ValidationError("Invalid invitation") from error
    if invitation.accepted_at is not None:
        raise ValidationError("Invitation has already been accepted")
    if invitation.revoked_at is not None:
        raise ValidationError("Invitation has been revoked")
    if invitation.expires_at <= now:
        raise ValidationError("Invitation has expired")
    if not invitation.organization.is_active:
        raise ValidationError("Organization is inactive")
    email = UserManager.normalize_login_email(invitation.email)
    if User.objects.filter(email=email).exists():
        raise ValidationError("An account already exists for this email. Sign in, then accept the invitation.")
    parts = full_name.split()
    first_name = parts[0]
    last_name = " ".join(parts[1:])
    candidate = User(email=email, first_name=first_name, last_name=last_name)
    validate_password(password, candidate)
    user = User.objects.create_user(email=email, password=password, first_name=first_name, last_name=last_name)
    membership = Membership.objects.create(user=user, organization=invitation.organization, role=invitation.role)
    invitation.accepted_at = now
    invitation.save(update_fields=("accepted_at", "updated_at"))
    return user, membership
