import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from notifications.models import Notification, NotificationRecipient
from notifications.services import (
    archive,
    create_notification,
    mark_all_read,
    mark_read,
    update_preferences,
)
from organizations.models import Membership, Organization
from users.models import User

pytestmark = pytest.mark.django_db(transaction=True)
PASSWORD = "Test-only-notification-credential-123"


def user(org, email, role="member", active=True):
    obj = User.objects.create_user(email=email, password=PASSWORD, is_active=active)
    Membership.objects.create(user=obj, organization=org, role=role)
    return obj


def test_model_recipient_uniqueness_action_url_and_state(client):
    org = Organization.objects.create(name="Notify", slug="notify")
    first = user(org, "first-notify@example.invalid")
    item = create_notification(
        organization=org,
        notification_type="booking.status_changed",
        category="bookings",
        title="Changed",
        message="EV reference changed.",
        users=[first],
        action_url="/workspace/bookings/00000000-0000-0000-0000-000000000001",
    )
    recipient = item.recipients.get()
    assert item.id and recipient.user == first
    with pytest.raises(IntegrityError):
        NotificationRecipient.objects.create(notification=item, user=first)
    mark_read(recipient)
    assert recipient.read_at
    mark_read(recipient, False)
    assert recipient.read_at is None
    mark_all_read(first)
    recipient.refresh_from_db()
    assert recipient.read_at
    archive(recipient)
    assert recipient.archived_at
    bad = Notification(
        notification_type="x",
        category="system",
        title="Bad",
        message="Bad",
        action_url="https://evil.invalid",
    )
    with pytest.raises(ValidationError):
        bad.save()


def test_access_isolation_preferences_and_inactive(client):
    org = Organization.objects.create(name="Notify two", slug="notify-two")
    first = user(org, "one-notify@example.invalid")
    second = user(org, "two-notify@example.invalid")
    inactive = user(org, "inactive-notify@example.invalid", active=False)
    update_preferences(second, {"bookings": False})
    item = create_notification(
        organization=org,
        notification_type="booking.status_changed",
        category="bookings",
        title="Safe",
        message="Status changed; no commercial amounts.",
        users=[first, second, inactive],
    )
    assert list(item.recipients.values_list("user", flat=True)) == [first.id]
    client.force_login(first)
    response = client.get("/api/notifications/")
    assert response.status_code == 200 and response.json()["count"] == 1
    assert (
        client.post(
            f"/api/notifications/{item.id}/read/", {"read": "not-a-boolean"}, format="json"
        ).status_code
        == 400
    )
    client.force_login(second)
    assert client.get("/api/notifications/").json()["count"] == 0
    assert client.post(f"/api/notifications/{item.id}/read/").status_code == 404


def test_actor_suppression_and_platform_authorization(client):
    org = Organization.objects.create(name="Notify three", slug="notify-three")
    actor = user(org, "actor-notify@example.invalid", "owner")
    staff = User.objects.create_user(
        email="staff-notify@example.invalid", password=PASSWORD, is_staff=True
    )
    assert (
        create_notification(
            organization=org,
            notification_type="x",
            category="system",
            title="Own",
            message="Own",
            users=[actor],
            actor=actor,
        )
        is None
    )
    client.force_login(staff)
    assert client.get("/api/platform/notifications/").status_code == 403
    root = User.objects.create_superuser(email="root-notify@example.invalid", password=PASSWORD)
    client.force_login(root)
    assert client.get("/api/platform/notifications/").status_code == 200


def test_inactive_membership_cannot_read_stale_organization_notification(client):
    org = Organization.objects.create(name="Stale notify", slug="stale-notify")
    recipient = user(org, "stale-notify@example.invalid")
    create_notification(
        organization=org,
        notification_type="task.assigned",
        category="team",
        title="Assigned",
        message="Task",
        users=[recipient],
    )
    membership = Membership.objects.get(user=recipient, organization=org)
    membership.is_active = False
    membership.save()
    client.force_login(recipient)
    response = client.get("/api/notifications/")
    assert response.status_code == 200
    assert response.json()["count"] == 0
