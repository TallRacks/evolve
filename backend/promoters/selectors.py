from audit.models import AuditEvent
from organizations.selectors import organizations_for_user

from .models import Promoter


def promoters_for_user(user):
    if user and user.is_authenticated and user.is_active and user.is_superuser:
        return Promoter.objects.select_related("organization").all()
    return Promoter.objects.filter(
        organization_id__in=organizations_for_user(user).values("pk")
    ).select_related("organization")


def promoter_activity(promoter):
    return AuditEvent.objects.filter(
        organization=promoter.organization,
        resource_type="Promoter",
        resource_id=str(promoter.pk),
        action__startswith="promoter.",
    ).select_related("actor")[:100]
