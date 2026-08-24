from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Membership, Organization

LAST_OWNER_MESSAGE = "An active organization must retain at least one active owner."


def effective_owners(organization, *, lock=False):
    queryset = Membership.objects.active().filter(
        organization=organization,
        role=Membership.Role.OWNER,
    )
    return queryset.select_for_update() if lock else queryset


@transaction.atomic
def validate_membership_owner_change(
    membership,
    *,
    role,
    is_active,
    user=None,
    organization=None,
):
    current_organization = Organization.objects.select_for_update().get(
        pk=membership.organization_id
    )
    if not current_organization.is_active:
        return

    current_user = membership.user
    current_is_effective = (
        membership.role == Membership.Role.OWNER and membership.is_active and current_user.is_active
    )
    next_user = user or current_user
    next_organization = organization or current_organization
    retains_effective_ownership = (
        next_organization.pk == current_organization.pk
        and role == Membership.Role.OWNER
        and is_active
        and next_user.is_active
    )
    if not current_is_effective or retains_effective_ownership:
        return

    if not effective_owners(current_organization, lock=True).exclude(pk=membership.pk).exists():
        raise ValidationError(LAST_OWNER_MESSAGE)


@transaction.atomic
def validate_user_deactivation(user, *, is_active):
    if not user.is_active or is_active:
        return

    owned_organization_ids = (
        Membership.objects.active()
        .filter(
            user=user,
            role=Membership.Role.OWNER,
        )
        .values("organization_id")
    )
    organizations = (
        Organization.objects.select_for_update()
        .filter(pk__in=owned_organization_ids)
        .order_by("pk")
    )
    blocked = [
        organization.name
        for organization in organizations
        if not effective_owners(organization, lock=True).exclude(user=user).exists()
    ]
    if blocked:
        names = ", ".join(sorted(blocked))
        raise ValidationError(f"{LAST_OWNER_MESSAGE} Affected: {names}.")
