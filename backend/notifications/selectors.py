from django.db.models import Q
from django.utils import timezone

from .models import NotificationRecipient


def inbox(user):
    queryset = NotificationRecipient.objects.filter(user=user, archived_at__isnull=True)
    if not getattr(user, "is_superuser", False):
        from organizations.models import Membership

        active_organizations = Membership.objects.active().filter(
            user=user, user__is_active=True, organization__is_active=True
        )
        queryset = queryset.filter(
            Q(notification__organization__isnull=True)
            | Q(notification__organization_id__in=active_organizations.values("organization_id"))
        )
    return queryset.filter(
        Q(notification__expires_at__isnull=True) | Q(notification__expires_at__gt=timezone.now())
    ).select_related("notification", "notification__organization")


def unread_count(user):
    return inbox(user).filter(read_at__isnull=True).count()
