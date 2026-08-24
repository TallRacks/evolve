from django.db.models import Q
from django.utils import timezone

from .models import NotificationRecipient


def inbox(user):
    return (
        NotificationRecipient.objects.filter(user=user, archived_at__isnull=True)
        .filter(
            Q(notification__expires_at__isnull=True)
            | Q(notification__expires_at__gt=timezone.now())
        )
        .select_related("notification", "notification__organization")
    )


def unread_count(user):
    return inbox(user).filter(read_at__isnull=True).count()
