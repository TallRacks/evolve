from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from audit.models import AuditEvent
from notifications.models import NotificationRecipient
from organizations.models import Membership, Organization
from tasks.models import Task
from tasks.services import (
    add_checklist_item,
    create_task,
    remove_checklist_item,
    set_checklist_completion,
    transition_task,
    update_checklist_item,
    update_task,
)
from users.models import User

pytestmark = pytest.mark.django_db
PASSWORD = "Task-test-password-123"


def membership(organization, email, role=Membership.Role.MANAGER, **user_values):
    user = User.objects.create_user(email=email, password=PASSWORD, **user_values)
    return Membership.objects.create(user=user, organization=organization, role=role)


def test_task_lifecycle_assignment_checklist_progress_audit_and_notification():
    organization = Organization.objects.create(name="Task Org", slug="task-org")
    manager = membership(organization, "manager@tasks.invalid")
    assignee = membership(organization, "assignee@tasks.invalid", Membership.Role.MEMBER)
    task = create_task(
        actor=manager.user,
        organization=organization,
        data={
            "title": "Deliver masters",
            "assigned_membership": assignee,
            "priority": Task.Priority.HIGH,
            "due_at": timezone.now() - timedelta(minutes=1),
        },
    )
    assert task.is_overdue
    assert NotificationRecipient.objects.filter(user=assignee.user).exists()
    item = add_checklist_item(actor=manager.user, task=task, title="Confirm files")
    second = add_checklist_item(actor=manager.user, task=task, title="Send files")
    update_checklist_item(
        actor=manager.user, item=second, data={"title": "Send approved files", "sequence": 1}
    )
    item.refresh_from_db()
    second.refresh_from_db()
    assert (second.sequence, item.sequence) == (1, 2)
    set_checklist_completion(actor=manager.user, item=item, complete=True)
    assert task.progress == {"complete": 1, "total": 2, "percent": 50}
    remove_checklist_item(actor=manager.user, item=second)
    assert task.progress == {"complete": 1, "total": 1, "percent": 100}
    done = transition_task(actor=manager.user, task=task, to_status=Task.Status.DONE)
    assert done.completed_by == manager.user
    assert not done.is_overdue
    reopened = transition_task(actor=manager.user, task=done, to_status=Task.Status.TODO)
    assert reopened.completed_at is None
    assert AuditEvent.objects.filter(resource_id=str(task.id), action="task.completed").exists()


def test_task_rejects_cross_org_inactive_assignment_and_generic_status_update():
    organization = Organization.objects.create(name="One", slug="task-one")
    other = Organization.objects.create(name="Two", slug="task-two")
    manager = membership(organization, "manager-one@tasks.invalid")
    outsider = membership(other, "outsider@tasks.invalid")
    with pytest.raises(ValidationError):
        create_task(
            actor=manager.user,
            organization=organization,
            data={"title": "No", "assigned_membership": outsider},
        )
    inactive = membership(organization, "inactive@tasks.invalid")
    inactive.is_active = False
    inactive.save()
    with pytest.raises(ValidationError):
        create_task(
            actor=manager.user,
            organization=organization,
            data={"title": "No", "assigned_membership": inactive},
        )
    task = create_task(actor=manager.user, organization=organization, data={"title": "Valid"})
    with pytest.raises(ValidationError):
        update_task(actor=manager.user, task=task, data={"status": Task.Status.DONE})


def test_staff_only_denied_and_superuser_cross_org_allowed():
    organization = Organization.objects.create(name="Scope", slug="task-scope")
    staff = User.objects.create_user(email="staff@tasks.invalid", password=PASSWORD, is_staff=True)
    with pytest.raises(PermissionDenied):
        create_task(actor=staff, organization=organization, data={"title": "Denied"})
    superuser = User.objects.create_superuser(email="root@tasks.invalid", password=PASSWORD)
    assert (
        create_task(
            actor=superuser, organization=organization, data={"title": "Allowed"}
        ).organization
        == organization
    )
