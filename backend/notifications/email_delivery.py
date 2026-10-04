# ruff: noqa: E501
from dataclasses import dataclass
from html import escape

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from integrations.models import EmailConnector
from integrations.services import send_application_email
from organizations.permissions import (
    user_has_organization_access,
    user_has_organization_permission,
)
from white_label.models import OrganizationDomain
from white_label.services import effective_branding

from .email_policy import CATEGORY_POLICIES, EMAIL_NOTIFICATION_TYPES
from .models import EmailDeliveryAttempt, Notification, NotificationPreference


@dataclass(frozen=True)
class RenderedEmail:
    template_key: str
    subject: str
    text: str
    html: str


def _origin(organization=None):
    if organization:
        domain = OrganizationDomain.objects.filter(
            organization=organization,
            verification_status=OrganizationDomain.VerificationStatus.VERIFIED,
            is_active=True,
            is_primary=True,
        ).first()
        if domain:
            return f"https://{domain.hostname}"
    return settings.EVOLVE_APP_ORIGIN.rstrip("/")


def _branding(organization):
    values = effective_branding(organization) if organization else {}
    logo = str(values.get("logo_url", ""))
    if logo.startswith("/"):
        logo = _origin(organization) + logo
    return {
        "name": values.get("brand_name") or "Evolve",
        "logo": logo if logo.startswith("https://") else "",
        "color": values.get("primary") or "#D6A84B",
    }


def _shell(*, organization, headline, content, action_label, action_url):
    brand = _branding(organization)
    safe_name = escape(brand["name"])
    safe_headline = escape(headline)
    safe_content = escape(content).replace("\n", "<br>")
    safe_url = escape(action_url, quote=True)
    logo = (
        f'<img src="{escape(brand["logo"], quote=True)}" alt="{safe_name}" width="120">'
        if brand["logo"]
        else f'<strong style="font-size:20px">{safe_name}</strong>'
    )
    # Email markup intentionally uses long, self-contained, email-safe table rows.
    html = f"""<!doctype html><html><body style="margin:0;background:#f5f5f5;color:#171717">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border:1px solid #ddd">
<tr><td style="padding:24px">{logo}</td></tr><tr><td style="padding:0 24px 24px"><h1 style="font-size:24px">{safe_headline}</h1><p>{safe_content}</p>
<p style="margin-top:24px"><a href="{safe_url}" style="background:{brand["color"]};color:#111;padding:12px 18px;text-decoration:none">{escape(action_label)}</a></p>
<p style="margin-top:24px;color:#666;font-size:12px">Sign in to Evolve to view authorized details. No tracking is used.</p></td></tr></table>
</td></tr></table></body></html>"""
    text = f"{brand['name']}\n\n{headline}\n\n{content}\n\n{action_label}: {action_url}\n"
    return text, html


def render_notification_email(notification):
    template_key = EMAIL_NOTIFICATION_TYPES[notification.notification_type]
    subjects = {
        "task_assigned": "A task was assigned to you",
        "task_reassigned": "A task was reassigned to you",
        "contract_approval_requested": "Contract approval requested",
        "call_sheet_published": "A Call Sheet was published",
        "invoice_issued": "An invoice was issued",
        "invoice_paid": "An invoice was paid",
    }
    labels = {
        "task_assigned": "Open task",
        "task_reassigned": "Open task",
        "contract_approval_requested": "Open contract",
        "call_sheet_published": "Open Call Sheet",
        "invoice_issued": "Open invoice",
        "invoice_paid": "Open invoice",
    }
    url = _origin(notification.organization) + notification.action_url
    text, html = _shell(
        organization=notification.organization,
        headline=subjects[template_key],
        content=notification.message,
        action_label=labels[template_key],
        action_url=url,
    )
    return RenderedEmail(template_key, subjects[template_key], text, html)


def render_invitation_email(invitation, token):
    subject = f"Invitation to join {invitation.organization.name} in Evolve"
    if "\n" in subject or "\r" in subject:
        raise ValidationError("Invalid organization name for email delivery.")
    url = f"{_origin(invitation.organization)}/invite/{token}"
    content = (
        f"You have been invited to join {invitation.organization.name}. "
        f"This invitation expires on {invitation.expires_at:%Y-%m-%d %H:%M %Z}."
    )
    text, html = _shell(
        organization=invitation.organization,
        headline="Organization invitation",
        content=content,
        action_label="Accept invitation",
        action_url=url,
    )
    return RenderedEmail("organization_invitation", subject[:220], text, html)


def resolve_connector():
    connector = (EmailConnector.objects.filter(is_active=True).order_by("-is_default", "-updated_at").first())
    return connector if connector and connector.secret_configured else None


def _authorized(notification, user):
    organization = notification.organization
    if not organization:
        return bool(user.is_active)
    if not user_has_organization_access(user, organization):
        return False
    permission = {
        "Task": "task.view",
        "Contract": "contract.view",
        "CallSheetVersion": "callsheet.view",
    }.get(notification.source_type)
    return not permission or user_has_organization_permission(user, organization, permission)


def _email_enabled(user, category):
    policy = CATEGORY_POLICIES[category]
    preference = NotificationPreference.objects.filter(user=user, category=category).first()
    return preference.email_enabled if preference else policy.default_email


def _create_attempt(**values):
    return EmailDeliveryAttempt.objects.create(**values)


def _deliver(
    *,
    rendered,
    recipient_email,
    category,
    organization=None,
    notification=None,
    user=None,
    attempt_number=1,
    idempotency_key=None,
    check_preference=True,
):
    existing = EmailDeliveryAttempt.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing
    base = {
        "notification": notification,
        "user": user,
        "organization": organization,
        "category": category,
        "template_key": rendered.template_key,
        "recipient_email_snapshot": recipient_email,
        "subject_snapshot": rendered.subject,
        "attempt_number": attempt_number,
        "idempotency_key": idempotency_key,
    }
    if user and (not user.is_active or not user.email):
        return _create_attempt(**base, status=EmailDeliveryAttempt.Status.SKIPPED)
    try:
        validate_email(recipient_email)
    except ValidationError:
        return _create_attempt(**base, status=EmailDeliveryAttempt.Status.SKIPPED)
    if notification and not _authorized(notification, user):
        return _create_attempt(**base, status=EmailDeliveryAttempt.Status.SUPPRESSED)
    if notification and check_preference and not _email_enabled(user, category):
        return _create_attempt(**base, status=EmailDeliveryAttempt.Status.SUPPRESSED)
    connector = resolve_connector()
    if not connector:
        return _create_attempt(**base, status=EmailDeliveryAttempt.Status.NOT_CONFIGURED)
    attempt = _create_attempt(
        **base, connector=connector, status=EmailDeliveryAttempt.Status.PENDING
    )
    try:
        send_application_email(
            connector, recipient_email, rendered.subject, rendered.text, rendered.html
        )
    except Exception as error:
        EmailDeliveryAttempt.objects.filter(pk=attempt.pk).update(
            status=EmailDeliveryAttempt.Status.FAILED,
            failure_code=error.__class__.__name__[:40],
            failure_message="Email provider rejected the message.",
        )
    else:
        EmailDeliveryAttempt.objects.filter(pk=attempt.pk).update(
            status=EmailDeliveryAttempt.Status.SENT, sent_at=timezone.now()
        )
    return EmailDeliveryAttempt.objects.get(pk=attempt.pk)


def deliver_notification_email(notification_id, user_id, attempt_number=1):
    try:
        notification = Notification.objects.select_related("organization").get(pk=notification_id)
        user = get_user_model().objects.get(pk=user_id)
        template_key = EMAIL_NOTIFICATION_TYPES.get(notification.notification_type)
        if not template_key:
            return None
        rendered = render_notification_email(notification)
        return _deliver(
            rendered=rendered,
            recipient_email=user.email,
            category=notification.category,
            organization=notification.organization,
            notification=notification,
            user=user,
            attempt_number=attempt_number,
            idempotency_key=(
                f"notification:{notification.pk}:user:{user.pk}:attempt:{attempt_number}"
            ),
        )
    except Exception:
        return None


def schedule_notification_email(notification, user_ids):
    for user_id in user_ids:
        transaction.on_commit(
            lambda notification_id=notification.pk, recipient_id=user_id: (
                deliver_notification_email(notification_id, recipient_id)
            )
        )


def deliver_invitation_email(invitation, token):
    rendered = render_invitation_email(invitation, token)
    return _deliver(
        rendered=rendered,
        recipient_email=invitation.email,
        category="team",
        organization=invitation.organization,
        idempotency_key=f"invitation:{invitation.pk}",
        check_preference=False,
    )


def schedule_invitation_email(invitation, token):
    transaction.on_commit(
        lambda invitation=invitation, token=token: deliver_invitation_email(invitation, token)
    )


def retry_delivery(attempt):
    if (
        attempt.status
        not in {
            EmailDeliveryAttempt.Status.FAILED,
            EmailDeliveryAttempt.Status.NOT_CONFIGURED,
        }
        or not attempt.notification_id
        or not attempt.user_id
    ):
        raise ValidationError("This delivery attempt cannot be retried.")
    latest = (
        EmailDeliveryAttempt.objects.filter(
            notification=attempt.notification, user=attempt.user
        ).aggregate(value=Max("attempt_number"))["value"]
        or 0
    )
    return deliver_notification_email(attempt.notification_id, attempt.user_id, latest + 1)
