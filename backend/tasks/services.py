from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from audit.services import record_event
from notifications.services import create_notification
from organizations.permissions import user_has_organization_permission

from .models import Task, TaskChecklistItem

TRANSITIONS = {
    Task.Status.TODO: {
        Task.Status.IN_PROGRESS,
        Task.Status.BLOCKED,
        Task.Status.DONE,
        Task.Status.CANCELLED,
    },
    Task.Status.IN_PROGRESS: {Task.Status.BLOCKED, Task.Status.DONE, Task.Status.CANCELLED},
    Task.Status.BLOCKED: {
        Task.Status.TODO,
        Task.Status.IN_PROGRESS,
        Task.Status.DONE,
        Task.Status.CANCELLED,
    },
    Task.Status.DONE: {Task.Status.TODO},
    Task.Status.CANCELLED: {Task.Status.TODO},
}


def require(actor, organization, permission):
    if not user_has_organization_permission(actor, organization, permission):
        raise PermissionDenied("You do not have permission for this task.")


def _event(actor, task, action, description, request=None):
    record_event(
        actor=actor,
        organization=task.organization,
        action=action,
        resource=task,
        description=description,
        request=request,
    )


def _notify_assignee(task, actor, action):
    memberships = list(task.additional_assignees.select_related("user"))
    if task.assigned_membership_id:
        memberships.insert(0, task.assigned_membership)
    if not memberships:
        return
    users = list({item.user_id: item.user for item in memberships}.values())
    create_notification(
        organization=task.organization,
        notification_type=action,
        category="team",
        title=action.replace("task.", "Task ").replace("_", " ").title(),
        message=task.title,
        users=users,
        actor=actor,
        source=task,
        action_url=f"/workspace/tasks/{task.pk}",
    )


def _validate_additional_assignees(organization, memberships):
    invalid = [
        membership
        for membership in memberships
        if membership.organization_id != organization.id
        or not membership.is_active
        or not membership.user.is_active
    ]
    if invalid:
        raise ValidationError("Additional assignees must be active members of the task organization.")


@transaction.atomic
def create_task(*, actor, organization, data, request=None):
    require(actor, organization, "task.manage")
    additional_assignees = data.pop("additional_assignees", [])
    _validate_additional_assignees(organization, additional_assignees)
    task = Task(organization=organization, created_by=actor, **data)
    task.save()
    task.additional_assignees.set(additional_assignees)
    _event(actor, task, "task.created", f"Created task {task.title}.", request)
    _notify_assignee(task, actor, "task.assigned")
    return task


@transaction.atomic
def update_task(*, actor, task, data, request=None):
    require(actor, task.organization, "task.manage")
    if "status" in data:
        raise ValidationError("Use a Task lifecycle action.")
    context_fields = {
        "artist",
        "booking",
        "release",
        "campaign",
        "rollout",
        "production_advance",
        "travel_itinerary",
        "contract",
    }
    supplied_contexts = context_fields.intersection(data)
    if supplied_contexts:
        for field in context_fields - supplied_contexts:
            setattr(task, field, None)
    previous_assignee = task.assigned_membership_id
    previous_additional = set(task.additional_assignees.values_list("pk", flat=True))
    additional_assignees = data.pop("additional_assignees", None)
    if additional_assignees is not None:
        _validate_additional_assignees(task.organization, additional_assignees)
    for field, value in data.items():
        setattr(task, field, value)
    task.save()
    if additional_assignees is not None:
        task.additional_assignees.set(additional_assignees)
    action = (
        "task.reassigned" if previous_assignee != task.assigned_membership_id or previous_additional != set(task.additional_assignees.values_list("pk", flat=True)) else "task.updated"
    )
    _event(actor, task, action, f"Updated task {task.title}.", request)
    if (
        previous_assignee != task.assigned_membership_id
        or previous_additional
        != set(task.additional_assignees.values_list("pk", flat=True))
    ):
        _notify_assignee(task, actor, action)
    return task


@transaction.atomic
def transition_task(*, actor, task, to_status, request=None):
    require(actor, task.organization, "task.status.manage")
    locked = Task.objects.select_for_update().get(pk=task.pk)
    if to_status not in TRANSITIONS[locked.status]:
        raise ValidationError(f"Task cannot change from {locked.status} to {to_status}.")
    locked.status = to_status
    if to_status == Task.Status.DONE:
        locked.completed_at, locked.completed_by = timezone.now(), actor
    else:
        locked.completed_at, locked.completed_by = None, None
    locked.full_clean()
    Task.objects.filter(pk=locked.pk).update(
        status=locked.status,
        completed_at=locked.completed_at,
        completed_by=locked.completed_by,
        updated_at=timezone.now(),
    )
    actions = {
        Task.Status.DONE: "task.completed",
        Task.Status.BLOCKED: "task.blocked",
        Task.Status.CANCELLED: "task.cancelled",
        Task.Status.TODO: "task.reopened",
        Task.Status.IN_PROGRESS: "task.started",
    }
    action = actions[to_status]
    _event(actor, locked, action, f"Task {locked.title} moved to {to_status}.", request)
    if action in {"task.blocked", "task.reopened"}:
        _notify_assignee(locked, actor, action)
    return locked


@transaction.atomic
def add_checklist_item(*, actor, task, title, sequence=None, request=None):
    require(actor, task.organization, "task.manage")
    if sequence is None:
        sequence = (
            task.checklist_items.filter(removed_at__isnull=True).aggregate(value=Max("sequence"))[
                "value"
            ]
            or 0
        ) + 1
    item = TaskChecklistItem(task=task, title=title, sequence=sequence)
    item.save()
    _event(
        actor,
        task,
        "task.checklist_item_added",
        f"Added a checklist item to {task.title}.",
        request,
    )
    return item


@transaction.atomic
def update_checklist_item(*, actor, item, data, request=None):
    require(actor, item.task.organization, "task.manage")
    locked = (
        TaskChecklistItem.objects.select_for_update()
        .select_related("task__organization")
        .get(pk=item.pk)
    )
    if "sequence" in data and data["sequence"] != locked.sequence:
        replacement = (
            TaskChecklistItem.objects.select_for_update()
            .filter(task=locked.task, sequence=data["sequence"], removed_at__isnull=True)
            .exclude(pk=locked.pk)
            .first()
        )
        if replacement:
            temporary = (
                locked.task.checklist_items.aggregate(value=Max("sequence"))["value"] or 0
            ) + 1
            TaskChecklistItem.objects.filter(pk=replacement.pk).update(sequence=temporary)
            previous = locked.sequence
            locked.sequence = data["sequence"]
            locked.save()
            TaskChecklistItem.objects.filter(pk=replacement.pk).update(sequence=previous)
        else:
            locked.sequence = data["sequence"]
    if "title" in data:
        locked.title = data["title"]
    locked.save()
    _event(
        actor,
        locked.task,
        "task.checklist_item_updated",
        f"Updated checklist progress for {locked.task.title}.",
        request,
    )
    return locked


@transaction.atomic
def set_checklist_completion(*, actor, item, complete, request=None):
    require(actor, item.task.organization, "task.manage")
    locked = (
        TaskChecklistItem.objects.select_for_update()
        .select_related("task__organization")
        .get(pk=item.pk)
    )
    locked.is_completed = complete
    locked.completed_at = timezone.now() if complete else None
    locked.completed_by = actor if complete else None
    locked.save()
    action = "task.checklist_item_completed" if complete else "task.checklist_item_reopened"
    _event(
        actor, locked.task, action, f"Updated checklist progress for {locked.task.title}.", request
    )
    return locked


@transaction.atomic
def remove_checklist_item(*, actor, item, request=None):
    require(actor, item.task.organization, "task.manage")
    item.removed_at = timezone.now()
    item.save(update_fields=("removed_at", "updated_at"))
    _event(
        actor,
        item.task,
        "task.checklist_item_removed",
        f"Removed a checklist item from {item.task.title}.",
        request,
    )
    return item
