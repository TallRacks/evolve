import json
import logging
import os

from django.db import transaction
from django.utils import timezone

from audit.services import record_event

from .email_policy import CATEGORY_POLICIES, EMAIL_NOTIFICATION_TYPES
from .models import DevicePushSubscription, Notification, NotificationPreference, NotificationRecipient

logger = logging.getLogger(__name__)


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
    ids.discard(getattr(actor, "pk", None))
    disabled = set(
        NotificationPreference.objects.filter(
            user_id__in=ids, category=category, in_app_enabled=False
        ).values_list("user_id", flat=True)
    )
    in_app_ids = ids - disabled
    email_eligible = notification_type in EMAIL_NOTIFICATION_TYPES
    if not in_app_ids and not (email_eligible and ids):
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
        [NotificationRecipient(notification=item, user_id=user_id) for user_id in in_app_ids],
        ignore_conflicts=True,
    )
    if email_eligible:
        from .email_delivery import schedule_notification_email

        schedule_notification_email(item, ids)
    transaction.on_commit(lambda: send_web_push(item, in_app_ids))
    return item


def send_web_push(notification, user_ids):
    """Best-effort self-hosted push; notification persistence never depends on delivery."""
    private_key = os.environ.get("EVOLVE_WEB_PUSH_PRIVATE_KEY", "")
    subject = os.environ.get("EVOLVE_WEB_PUSH_SUBJECT", "")
    if not private_key or not subject or not user_ids:
        return
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("Web Push dependency is not installed")
        return
    payload = json.dumps({
        "title": notification.title,
        "body": notification.message,
        "url": notification.action_url or "/workspace/notifications",
        "priority": notification.priority,
    })
    subscriptions = DevicePushSubscription.objects.filter(user_id__in=user_ids, is_active=True)
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
            )
        except WebPushException as exc:
            if getattr(exc.response, "status_code", None) in (404, 410):
                subscription.is_active = False
                subscription.save(update_fields=("is_active", "updated_at"))
            else:
                logger.warning("Web Push delivery failed for device %s", subscription.id)
        except Exception:
            logger.warning("Web Push delivery failed for device %s", subscription.id, exc_info=True)


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


def preference_rows(user):
    current = {item.category: item for item in NotificationPreference.objects.filter(user=user)}
    return [
        {
            "category": policy.key,
            "label": policy.label,
            "description": policy.description,
            "in_app_enabled": (
                current[policy.key].in_app_enabled
                if policy.key in current
                else policy.default_in_app
            ),
            "email_enabled": (
                current[policy.key].email_enabled if policy.key in current else policy.default_email
            ),
            "in_app_disableable": policy.in_app_disableable,
            "email_disableable": policy.email_disableable,
        }
        for policy in CATEGORY_POLICIES.values()
    ]


def update_preferences(user, values, request=None):
    for category, value in values.items():
        policy = CATEGORY_POLICIES[category]
        supplied = value if isinstance(value, dict) else {"in_app_enabled": value}
        existing = NotificationPreference.objects.filter(user=user, category=category).first()
        defaults = {
            "in_app_enabled": supplied.get(
                "in_app_enabled", existing.in_app_enabled if existing else policy.default_in_app
            ),
            "email_enabled": supplied.get(
                "email_enabled", existing.email_enabled if existing else policy.default_email
            ),
        }
        if not policy.in_app_disableable:
            defaults["in_app_enabled"] = True
        if not policy.email_disableable:
            defaults["email_enabled"] = True
        NotificationPreference.objects.update_or_create(
            user=user, category=category, defaults=defaults
        )
    record_event(
        actor=user,
        organization=None,
        action="notification.preference_updated",
        resource=user,
        description="Updated notification delivery preferences.",
        request=request,
    )


def reset_preferences(user, request=None):
    NotificationPreference.objects.filter(user=user).delete()
    record_event(
        actor=user,
        organization=None,
        action="notification.preference_reset",
        resource=user,
        description="Reset notification delivery preferences to defaults.",
        request=request,
    )
    return preference_rows(user)
