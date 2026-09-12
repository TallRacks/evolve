import json
from unittest.mock import Mock

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings

from integrations.models import EmailConnector
from notifications.email_delivery import (
    deliver_notification_email,
    render_invitation_email,
    render_notification_email,
)
from notifications.models import EmailDeliveryAttempt, Notification, NotificationPreference
from notifications.services import (
    create_notification,
    preference_rows,
    reset_preferences,
    update_preferences,
)
from organizations.models import Membership, Organization
from organizations.services import create_invitation
from users.models import User

pytestmark = pytest.mark.django_db(transaction=True)
PASSWORD = "Test-only-email-credential-123"


def member(organization, email, role="member"):
    user = User.objects.create_user(email=email, password=PASSWORD)
    Membership.objects.create(user=user, organization=organization, role=role)
    return user


def connector(monkeypatch, created_by):
    monkeypatch.setenv("EVOLVE_EMAIL_TEST_SECRET", "test-only")
    return EmailConnector.objects.create(
        name="Test SMTP",
        is_active=True,
        is_default=True,
        from_name="Evolve",
        from_email="no-reply@example.invalid",
        host="smtp.example.invalid",
        port=587,
        use_tls=True,
        secret_reference="EVOLVE_EMAIL_TEST_SECRET",
        created_by=created_by,
    )


def notification_for(organization, recipient):
    return create_notification(
        organization=organization,
        notification_type="task.assigned",
        category=Notification.Category.TEAM,
        title="Task assigned",
        message="Review the production plan.",
        users=[recipient],
        action_url="/workspace/tasks",
    )


def test_preference_defaults_partial_update_reset_and_security_policy():
    organization = Organization.objects.create(name="Preference Org", slug="preference-org")
    recipient = member(organization, "preference@example.invalid")
    rows = {row["category"]: row for row in preference_rows(recipient)}
    assert rows["team"]["email_enabled"] is True
    assert rows["bookings"]["email_enabled"] is False
    assert rows["security"]["email_disableable"] is False

    update_preferences(recipient, {"team": {"email_enabled": False}})
    preference = NotificationPreference.objects.get(user=recipient, category="team")
    assert preference.in_app_enabled is True
    assert preference.email_enabled is False

    update_preferences(
        recipient,
        {"security": {"in_app_enabled": False, "email_enabled": False}},
    )
    security = NotificationPreference.objects.get(user=recipient, category="security")
    assert security.in_app_enabled is True
    assert security.email_enabled is True
    assert reset_preferences(recipient) == preference_rows(recipient)
    assert not NotificationPreference.objects.filter(user=recipient).exists()


def test_notification_without_connector_is_logged_and_idempotent():
    organization = Organization.objects.create(name="No Mail", slug="no-mail")
    recipient = member(organization, "no-mail@example.invalid")
    notification = notification_for(organization, recipient)
    attempt = EmailDeliveryAttempt.objects.get(notification=notification, user=recipient)
    assert attempt.status == EmailDeliveryAttempt.Status.NOT_CONFIGURED
    assert deliver_notification_email(notification.pk, recipient.pk).pk == attempt.pk
    assert (
        EmailDeliveryAttempt.objects.filter(notification=notification, user=recipient).count() == 1
    )


def test_success_failure_and_retry_are_honest(monkeypatch):
    organization = Organization.objects.create(name="Mail", slug="mail")
    recipient = member(organization, "mail@example.invalid")
    connector(monkeypatch, recipient)
    sender = Mock()
    monkeypatch.setattr("notifications.email_delivery.send_application_email", sender)

    notification = notification_for(organization, recipient)
    first = EmailDeliveryAttempt.objects.get(notification=notification, user=recipient)
    assert first.status == EmailDeliveryAttempt.Status.SENT
    assert first.sent_at is not None
    sender.assert_called_once()

    second = Notification.objects.create(
        organization=organization,
        notification_type="task.assigned",
        category=Notification.Category.TEAM,
        title="Another task",
        message="Review the itinerary.",
        action_url="/workspace/tasks",
    )
    sender.side_effect = ValidationError("provider failed")
    failed = deliver_notification_email(second.pk, recipient.pk)
    assert failed.status == EmailDeliveryAttempt.Status.FAILED
    assert failed.failure_message == "Email provider rejected the message."
    assert "provider failed" not in failed.failure_message


def test_disabled_email_is_suppressed_without_affecting_in_app():
    organization = Organization.objects.create(name="Opt Out", slug="opt-out")
    recipient = member(organization, "opt-out@example.invalid")
    update_preferences(recipient, {"team": {"email_enabled": False}})
    notification = notification_for(organization, recipient)
    assert notification.recipients.filter(user=recipient).exists()
    assert (
        EmailDeliveryAttempt.objects.get(notification=notification, user=recipient).status
        == EmailDeliveryAttempt.Status.SUPPRESSED
    )


@override_settings(EVOLVE_APP_ORIGIN="https://evolve.example.invalid")
def test_templates_escape_content_and_include_plain_text():
    organization = Organization.objects.create(name="Safe Org", slug="safe-org")
    recipient = member(organization, "safe@example.invalid")
    notification = Notification.objects.create(
        organization=organization,
        notification_type="task.assigned",
        category=Notification.Category.TEAM,
        title="Task",
        message="<script>alert('x')</script>",
        action_url="/workspace/tasks",
    )
    rendered = render_notification_email(notification)
    assert "<script>" not in rendered.html
    assert "&lt;script&gt;" in rendered.html
    assert "https://evolve.example.invalid/workspace/tasks" in rendered.text
    assert "tracking" in rendered.html.lower()
    assert recipient.email not in rendered.html


def test_invitation_token_is_only_in_rendered_link_not_delivery_log():
    organization = Organization.objects.create(name="Invite Org", slug="invite-org")
    owner = member(organization, "owner@example.invalid", "owner")
    created = create_invitation(
        organization=organization,
        email="invited@example.invalid",
        role="member",
        invited_by=owner,
    )
    attempt = EmailDeliveryAttempt.objects.get(
        idempotency_key=f"invitation:{created.invitation.pk}"
    )
    assert attempt.status == EmailDeliveryAttempt.Status.NOT_CONFIGURED
    assert created.token not in attempt.subject_snapshot
    assert created.token not in repr(attempt.__dict__)
    rendered = render_invitation_email(created.invitation, created.token)
    assert created.token in rendered.text
    assert created.invitation.token_digest != created.token


def test_delivery_log_is_platform_superuser_only(client):
    organization = Organization.objects.create(name="Log Org", slug="log-org")
    staff = User.objects.create_user(
        email="staff-log@example.invalid", password=PASSWORD, is_staff=True
    )
    root = User.objects.create_superuser(email="root-log@example.invalid", password=PASSWORD)
    member(organization, "ordinary-log@example.invalid")

    client.force_login(staff)
    assert client.get("/api/platform/email-deliveries/").status_code == 403
    client.force_login(root)
    assert client.get("/api/platform/email-deliveries/").status_code == 200


def test_delivery_attempt_is_append_only():
    attempt = EmailDeliveryAttempt.objects.create(
        category="team",
        template_key="test",
        recipient_email_snapshot="append-only@example.invalid",
        subject_snapshot="Test",
        status=EmailDeliveryAttempt.Status.SKIPPED,
        idempotency_key="append-only-test",
    )
    attempt.status = EmailDeliveryAttempt.Status.SENT
    with pytest.raises(ValidationError):
        attempt.save()
    with pytest.raises(ValidationError):
        attempt.delete()


def test_preference_api_is_user_scoped_and_supports_partial_updates(client):
    organization = Organization.objects.create(name="API Pref", slug="api-pref")
    first = member(organization, "first-pref@example.invalid")
    second = member(organization, "second-pref@example.invalid")
    client.force_login(first)

    response = client.get("/api/notification-preferences/")
    assert response.status_code == 200
    assert {item["category"] for item in response.json()} == set(Notification.Category.values)

    response = client.patch(
        "/api/notification-preferences/",
        json.dumps([{"category": "team", "email_enabled": False}]),
        content_type="application/json",
    )
    assert response.status_code == 200
    saved = NotificationPreference.objects.get(user=first, category="team")
    assert saved.in_app_enabled is True
    assert saved.email_enabled is False
    assert not NotificationPreference.objects.filter(user=second).exists()

    assert client.post("/api/notification-preferences/reset/").status_code == 200
    assert not NotificationPreference.objects.filter(user=first).exists()


def test_platform_retry_creates_a_new_attempt_and_audit(client):
    organization = Organization.objects.create(name="Retry Org", slug="retry-org")
    recipient = member(organization, "retry@example.invalid")
    root = User.objects.create_superuser(email="retry-root@example.invalid", password=PASSWORD)
    notification = notification_for(organization, recipient)
    first = EmailDeliveryAttempt.objects.get(notification=notification, user=recipient)
    client.force_login(root)

    response = client.post(f"/api/platform/email-deliveries/{first.pk}/retry/")
    assert response.status_code == 201
    assert response.json()["attempt_number"] == 2
    assert response.json()["status"] == "not_configured"
    assert (
        EmailDeliveryAttempt.objects.filter(notification=notification, user=recipient).count() == 2
    )
