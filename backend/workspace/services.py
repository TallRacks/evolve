from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from audit.services import record_event
from organizations.permissions import user_has_organization_permission
from tasks.models import Task
from tasks.services import create_task, transition_task

from .models import ActionRequest

HIGH_RISK_ACTIONS = {"finance.issue_invoice", "finance.record_payment", "finance.void_payment", "rights.modify_ownership", "royalties.finalize", "contracts.execute", "contracts.terminate", "users.deactivate", "users.change_role", "permissions.change", "organization.change_owner"}
ACTION_RISKS = {"tasks.list": "read", "bookings.upcoming": "read", "booking.summary": "read", "artist.summary": "read", "calendar.today": "read", "notifications.unread": "read", "tasks.create": "low", "tasks.complete": "low", "calendar.create_event": "low", "tasks.assign": "medium", "callsheets.generate": "medium", "bookings.prepare_operations": "medium", "production.create": "medium", "travel.create": "medium"}


def propose_action(*, actor, organization, channel, action_key, payload, idempotency_key):
    risk_value = ACTION_RISKS.get(action_key)
    if not risk_value:
        risk_value = "high" if action_key in HIGH_RISK_ACTIONS else None
    if not risk_value:
        raise ValueError("Unsupported action.")
    risk = ActionRequest.Risk(risk_value)
    if risk == ActionRequest.Risk.HIGH:
        return ActionRequest.objects.create(actor=actor, organization=organization, channel=channel, action_key=action_key, risk=risk, validated_payload={}, status=ActionRequest.Status.BLOCKED, expires_at=timezone.now(), result_summary="This action must be completed inside Evolve.", idempotency_key=idempotency_key)
    if not user_has_organization_permission(actor, organization, "task.view"):
        raise PermissionError("Organization access required.")
    expires_at = timezone.now() + timedelta(minutes=10)
    confirmation_hash = ActionRequest.make_confirmation_hash(actor_id=actor.pk, organization_id=organization.pk, channel=channel, action_key=action_key, payload=payload, expires_at=expires_at)
    request, _ = ActionRequest.objects.get_or_create(idempotency_key=idempotency_key, defaults={"actor": actor, "organization": organization, "channel": channel, "action_key": action_key, "risk": risk, "validated_payload": payload, "confirmation_hash": confirmation_hash, "expires_at": expires_at})
    return request


@transaction.atomic
def execute_action(*, action_request_id, actor, confirmation_hash=None, channel=None):
    action = ActionRequest.objects.select_for_update().select_related("organization").get(pk=action_request_id)
    now = timezone.now()
    if action.actor_id != actor.pk or not actor.memberships.filter(is_active=True, organization_id=action.organization_id).exists():
        raise PermissionError("Action context does not match.")
    if channel is not None and action.channel != channel:
        raise PermissionError("Action channel does not match.")
    if action.status != ActionRequest.Status.PROPOSED:
        raise ValueError("Action is no longer executable.")
    if action.expires_at <= now:
        action.status = ActionRequest.Status.EXPIRED
        action.save(update_fields=["status", "updated_at"])
        raise ValueError("Action confirmation expired.")
    if action.risk != ActionRequest.Risk.READ and confirmation_hash != action.confirmation_hash:
        raise PermissionError("Confirmation does not match this action.")
    payload = action.validated_payload
    if action.action_key == "tasks.create":
        task = create_task(actor=actor, organization=action.organization, data=payload)
        summary = f"Created task: {task.title}"
    elif action.action_key == "tasks.complete":
        task = Task.objects.get(pk=payload["task_id"], organization=action.organization)
        transition_task(actor=actor, task=task, to_status=Task.Status.DONE)
        summary = f"Completed task: {task.title}"
    else:
        summary = "Read-only action completed." if action.risk == ActionRequest.Risk.READ else "Action proposed for domain service execution."
    action.status = ActionRequest.Status.EXECUTED
    action.executed_at = now
    action.result_summary = summary
    action.save(update_fields=["status", "executed_at", "result_summary", "updated_at"])
    record_event(actor=actor, organization=action.organization, action="workspace.action.executed", resource=action, description=summary)
    return action
