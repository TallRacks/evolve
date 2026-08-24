from django.db import transaction
from django.utils import timezone

from audit.services import record_event

from .models import Notification, NotificationPreference, NotificationRecipient


def active_users(users, organization=None):
    ids = {user.pk for user in users if user and user.is_active}
    if organization:
        from organizations.models import Membership

        ids &= set(
            Membership.objects.active()
            .filter(organization=organization, user_id__in=ids, user__is_active=True)
            .values_list("user_id", flat=True)
        )
    return ids


@transaction.atomic
def create_notification(
    *,
    organization,
    notification_type,
    category,
    title,
    message,
    users,
    actor=None,
    priority="normal",
    source=None,
    action_url="",
):
    ids = active_users(users, organization)
    disabled = set(
        NotificationPreference.objects.filter(
            user_id__in=ids, category=category, in_app_enabled=False
        ).values_list("user_id", flat=True)
    )
    ids -= disabled
    ids.discard(getattr(actor, "pk", None))
    if not ids:
        return None
    item = Notification(
        organization=organization,
        notification_type=notification_type,
        category=category,
        title=title,
        message=message,
        priority=priority,
        source_type=source.__class__.__name__ if source else "",
        source_id=str(source.pk) if source else "",
        action_url=action_url,
        actor=actor,
    )
    item.save()
    NotificationRecipient.objects.bulk_create(
        [NotificationRecipient(notification=item, user_id=user_id) for user_id in ids],
        ignore_conflicts=True,
    )
    return item


def booking_team_users(booking):
    return [
        assignment.membership.user
        for assignment in booking.team_assignments.filter(is_active=True).select_related(
            "membership__user"
        )
        if assignment.membership.is_active
    ]


def artist_team_users(artist):
    return [
        assignment.membership.user
        for assignment in artist.team_assignments.filter(is_active=True).select_related(
            "membership__user"
        )
        if assignment.membership.is_active
    ]


def mark_read(recipient, read=True):
    recipient.read_at = timezone.now() if read else None
    recipient.save(update_fields=("read_at",))
    return recipient


def mark_all_read(user):
    return NotificationRecipient.objects.filter(
        user=user, archived_at__isnull=True, read_at__isnull=True
    ).update(read_at=timezone.now())


def archive(recipient):
    recipient.archived_at = timezone.now()
    recipient.save(update_fields=("archived_at",))
    return recipient


def update_preferences(user, values, request=None):
    for category, enabled in values.items():
        NotificationPreference.objects.update_or_create(
            user=user, category=category, defaults={"in_app_enabled": enabled}
        )
    record_event(
        actor=user,
        organization=None,
        action="notification.preference_updated",
        resource=user,
        description="Updated in-app notification preferences.",
        request=request,
    )
