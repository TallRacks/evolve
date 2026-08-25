from organizations.models import Membership, Organization
from organizations.permissions import user_has_organization_permission

from .models import RightsParty, RoyaltyStatement, Work


def organization_ids(user, permission):
    if user.is_superuser:
        return None
    candidates = Organization.objects.filter(
        memberships__in=Membership.objects.active().filter(user=user)
    ).distinct()
    return [
        organization.id
        for organization in candidates
        if user_has_organization_permission(user, organization, permission)
    ]


def works_for_user(user):
    ids = organization_ids(user, "rights.view")
    queryset = Work.objects.all()
    return queryset if ids is None else queryset.filter(organization_id__in=ids)


def parties_for_user(user):
    ids = organization_ids(user, "rights.view")
    queryset = RightsParty.objects.all()
    return queryset if ids is None else queryset.filter(organization_id__in=ids)


def statements_for_user(user):
    ids = organization_ids(user, "royalties.view")
    queryset = RoyaltyStatement.objects.all()
    return queryset if ids is None else queryset.filter(organization_id__in=ids)
