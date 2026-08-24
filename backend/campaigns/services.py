from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_event
from organizations.permissions import user_has_organization_permission

from .models import (
    Campaign,
    CampaignChannel,
    Rollout,
    RolloutMilestone,
    RolloutTask,
    RolloutTaskDependency,
)

CAMPAIGN_TRANSITIONS = {
    Campaign.Status.DRAFT: {Campaign.Status.PLANNED, Campaign.Status.CANCELLED},
    Campaign.Status.PLANNED: {
        Campaign.Status.ACTIVE,
        Campaign.Status.DRAFT,
        Campaign.Status.CANCELLED,
    },
    Campaign.Status.ACTIVE: {
        Campaign.Status.PAUSED,
        Campaign.Status.COMPLETED,
        Campaign.Status.CANCELLED,
    },
    Campaign.Status.PAUSED: {Campaign.Status.ACTIVE, Campaign.Status.CANCELLED},
    Campaign.Status.COMPLETED: {Campaign.Status.ARCHIVED},
    Campaign.Status.CANCELLED: {Campaign.Status.ARCHIVED},
    Campaign.Status.ARCHIVED: set(),
}
ROLLOUT_TRANSITIONS = {
    Rollout.Status.DRAFT: {Rollout.Status.ACTIVE, Rollout.Status.CANCELLED},
    Rollout.Status.ACTIVE: {Rollout.Status.COMPLETED, Rollout.Status.CANCELLED},
    Rollout.Status.COMPLETED: {Rollout.Status.ARCHIVED},
    Rollout.Status.CANCELLED: {Rollout.Status.ARCHIVED},
    Rollout.Status.ARCHIVED: set(),
}
TASK_TRANSITIONS = {
    RolloutTask.Status.TODO: {
        RolloutTask.Status.IN_PROGRESS,
        RolloutTask.Status.BLOCKED,
        RolloutTask.Status.CANCELLED,
    },
    RolloutTask.Status.IN_PROGRESS: {
        RolloutTask.Status.TODO,
        RolloutTask.Status.BLOCKED,
        RolloutTask.Status.CANCELLED,
    },
    RolloutTask.Status.BLOCKED: {
        RolloutTask.Status.TODO,
        RolloutTask.Status.IN_PROGRESS,
        RolloutTask.Status.CANCELLED,
    },
    RolloutTask.Status.DONE: {RolloutTask.Status.TODO, RolloutTask.Status.IN_PROGRESS},
    RolloutTask.Status.CANCELLED: set(),
}


def require(actor, org, permission):
    if not user_has_organization_permission(actor, org, permission):
        raise PermissionDenied("You do not have permission for this campaign plan.")


def emit(actor, org, action, resource, description, request=None):
    record_event(
        actor=actor,
        organization=org,
        action=action,
        resource=resource,
        description=description,
        request=request,
    )


def mutate(instance, data):
    for key, value in data.items():
        setattr(instance, key, value)
    instance.save()
    return instance


@transaction.atomic
def create_campaign(*, actor, organization, data, request=None):
    require(actor, organization, "campaign.manage")
    obj = Campaign(organization=organization, created_by=actor, **data)
    obj.save()
    emit(actor, organization, "campaign.created", obj, f"Created campaign {obj.name}.", request)
    return obj


@transaction.atomic
def update_campaign(*, actor, campaign, data, request=None):
    require(actor, campaign.organization, "campaign.manage")
    if "status" in data:
        raise ValidationError("Use Campaign lifecycle service.")
    mutate(campaign, data)
    emit(
        actor,
        campaign.organization,
        "campaign.updated",
        campaign,
        f"Updated campaign {campaign.name}.",
        request,
    )
    return campaign


@transaction.atomic
def transition_campaign(*, actor, campaign, to_status, request=None):
    require(actor, campaign.organization, "campaign.status.manage")
    obj = Campaign.objects.select_for_update().get(pk=campaign.pk)
    if to_status not in CAMPAIGN_TRANSITIONS[obj.status]:
        raise ValidationError(f"Cannot transition Campaign from {obj.status} to {to_status}.")
    old = obj.status
    Campaign.objects.filter(pk=obj.pk).update(status=to_status)
    obj.refresh_from_db()
    emit(
        actor,
        obj.organization,
        "campaign.archived" if to_status == Campaign.Status.ARCHIVED else "campaign.status_changed",
        obj,
        f"Changed campaign {obj.name} from {old} to {to_status}.",
        request,
    )
    return obj


@transaction.atomic
def add_channel(*, actor, campaign, data, request=None):
    require(actor, campaign.organization, "campaign.manage")
    obj = CampaignChannel(campaign=campaign, **data)
    obj.full_clean()
    obj.save()
    emit(
        actor,
        campaign.organization,
        "campaign.channel_added",
        campaign,
        "Added a campaign channel.",
        request,
    )
    return obj


@transaction.atomic
def remove_channel(*, actor, channel, request=None):
    require(actor, channel.campaign.organization, "campaign.manage")
    campaign = channel.campaign
    channel.delete()
    emit(
        actor,
        campaign.organization,
        "campaign.channel_removed",
        campaign,
        "Removed a campaign channel.",
        request,
    )


@transaction.atomic
def create_rollout(*, actor, campaign, data, request=None):
    require(actor, campaign.organization, "rollout.manage")
    obj = Rollout(organization=campaign.organization, campaign=campaign, created_by=actor, **data)
    obj.save()
    emit(actor, obj.organization, "rollout.created", obj, f"Created rollout {obj.name}.", request)
    return obj


@transaction.atomic
def update_rollout(*, actor, rollout, data, request=None):
    require(actor, rollout.organization, "rollout.manage")
    if "status" in data:
        raise ValidationError("Use Rollout lifecycle service.")
    mutate(rollout, data)
    emit(
        actor,
        rollout.organization,
        "rollout.updated",
        rollout,
        f"Updated rollout {rollout.name}.",
        request,
    )
    return rollout


@transaction.atomic
def transition_rollout(*, actor, rollout, to_status, request=None):
    require(actor, rollout.organization, "rollout.manage")
    obj = Rollout.objects.select_for_update().get(pk=rollout.pk)
    if to_status not in ROLLOUT_TRANSITIONS[obj.status]:
        raise ValidationError(f"Cannot transition Rollout from {obj.status} to {to_status}.")
    old = obj.status
    Rollout.objects.filter(pk=obj.pk).update(status=to_status)
    obj.refresh_from_db()
    emit(
        actor,
        obj.organization,
        "rollout.status_changed",
        obj,
        f"Changed rollout {obj.name} from {old} to {to_status}.",
        request,
    )
    return obj


@transaction.atomic
def create_milestone(*, actor, rollout, data, request=None):
    require(actor, rollout.organization, "rollout.manage")
    obj = RolloutMilestone(rollout=rollout, **data)
    obj.save()
    emit(
        actor,
        rollout.organization,
        "rollout.milestone_created",
        rollout,
        "Created rollout milestone.",
        request,
    )
    return obj


@transaction.atomic
def update_milestone(*, actor, milestone, data, request=None):
    require(actor, milestone.rollout.organization, "rollout.manage")
    mutate(milestone, data)
    emit(
        actor,
        milestone.rollout.organization,
        "rollout.milestone_updated",
        milestone.rollout,
        "Updated rollout milestone.",
        request,
    )
    return milestone


@transaction.atomic
def remove_milestone(*, actor, milestone, request=None):
    require(actor, milestone.rollout.organization, "rollout.manage")
    if milestone.tasks.exists():
        raise ValidationError("Move tasks before removing this milestone.")
    rollout = milestone.rollout
    milestone.delete()
    emit(
        actor,
        rollout.organization,
        "rollout.milestone_removed",
        rollout,
        "Removed rollout milestone.",
        request,
    )


@transaction.atomic
def create_task(*, actor, rollout, data, request=None):
    require(actor, rollout.organization, "rollout.task.manage")
    obj = RolloutTask(rollout=rollout, **data)
    obj.save()
    emit(
        actor,
        rollout.organization,
        "rollout.task_created",
        rollout,
        "Created rollout task.",
        request,
    )
    return obj


@transaction.atomic
def update_task(*, actor, task, data, request=None):
    require(actor, task.rollout.organization, "rollout.task.manage")
    if "status" in data:
        raise ValidationError("Use Task lifecycle service.")
    mutate(task, data)
    emit(
        actor,
        task.rollout.organization,
        "rollout.task_updated",
        task.rollout,
        "Updated rollout task.",
        request,
    )
    return task


@transaction.atomic
def transition_task(*, actor, task, to_status, request=None):
    require(actor, task.rollout.organization, "rollout.task.manage")
    obj = RolloutTask.objects.select_for_update().get(pk=task.pk)
    if to_status == RolloutTask.Status.DONE:
        raise ValidationError("Use Task completion service.")
    if to_status not in TASK_TRANSITIONS[obj.status]:
        raise ValidationError(f"Cannot transition Task from {obj.status} to {to_status}.")
    old = obj.status
    RolloutTask.objects.filter(pk=obj.pk).update(
        status=to_status, completed_at=None, completed_by=None
    )
    obj.refresh_from_db()
    action = (
        "rollout.task_reopened"
        if old == RolloutTask.Status.DONE
        else "rollout.task_cancelled"
        if to_status == RolloutTask.Status.CANCELLED
        else "rollout.task_status_changed"
    )
    emit(
        actor,
        obj.rollout.organization,
        action,
        obj.rollout,
        f"Changed task status from {old} to {to_status}.",
        request,
    )
    return obj


@transaction.atomic
def complete_task(*, actor, task, request=None):
    require(actor, task.rollout.organization, "rollout.task.manage")
    obj = RolloutTask.objects.select_for_update().get(pk=task.pk)
    if obj.status in (RolloutTask.Status.DONE, RolloutTask.Status.CANCELLED):
        raise ValidationError("Task cannot be completed from its current status.")
    now = timezone.now()
    RolloutTask.objects.filter(pk=obj.pk).update(
        status=RolloutTask.Status.DONE, completed_at=now, completed_by=actor
    )
    obj.refresh_from_db()
    emit(
        actor,
        obj.rollout.organization,
        "rollout.task_completed",
        obj.rollout,
        "Completed rollout task.",
        request,
    )
    return obj


@transaction.atomic
def add_dependency(*, actor, task, depends_on, request=None):
    require(actor, task.rollout.organization, "rollout.task.manage")
    obj = RolloutTaskDependency(task=task, depends_on=depends_on)
    obj.save()
    emit(
        actor,
        task.rollout.organization,
        "rollout.dependency_added",
        task.rollout,
        "Added task dependency.",
        request,
    )
    return obj


@transaction.atomic
def remove_dependency(*, actor, dependency, request=None):
    require(actor, dependency.task.rollout.organization, "rollout.task.manage")
    rollout = dependency.task.rollout
    dependency.delete()
    emit(
        actor,
        rollout.organization,
        "rollout.dependency_removed",
        rollout,
        "Removed task dependency.",
        request,
    )
