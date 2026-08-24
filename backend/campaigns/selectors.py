from artists.selectors import portal_artists_for_user
from audit.models import AuditEvent
from organizations.selectors import organizations_for_user

from .models import Campaign, Rollout


def campaigns_for_user(user):
    if user and user.is_authenticated and user.is_active and user.is_superuser:
        return Campaign.objects.all()
    return Campaign.objects.filter(organization_id__in=organizations_for_user(user).values("pk"))


def rollouts_for_user(user):
    if user and user.is_authenticated and user.is_active and user.is_superuser:
        return Rollout.objects.all()
    return Rollout.objects.filter(organization_id__in=organizations_for_user(user).values("pk"))


def portal_campaigns(user):
    return Campaign.objects.filter(
        artist_id__in=portal_artists_for_user(user).values("pk"),
        status__in=(
            Campaign.Status.PLANNED,
            Campaign.Status.ACTIVE,
            Campaign.Status.PAUSED,
            Campaign.Status.COMPLETED,
        ),
    )


def activity(resource):
    return AuditEvent.objects.filter(
        organization=resource.organization, resource_id=str(resource.pk)
    ).select_related("actor")[:100]
