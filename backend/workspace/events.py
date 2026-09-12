import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone

from audit.services import record_event
from organizations.models import Membership
from notifications.services import create_notification

from .automation_models import AutomationExecution
from .models import Automation

ALLOWED_ACTIONS = {"notify.assignee", "notify.team", "notify.approver", "callsheet.create_draft", "task.create"}
MAX_AUTOMATION_DEPTH = 3


def emit_event(*, event_key, organization, actor=None, payload=None, correlation_id=None, depth=0):
    """Queue an explicitly emitted domain event after its transaction commits."""
    correlation_id = correlation_id or uuid.uuid4()
    payload = payload or {}

    def dispatch():
        for automation in Automation.objects.filter(organization=organization, event_key=event_key, is_active=True):
            execute_automation(automation=automation, event_key=event_key, organization=organization, actor=actor, payload=payload, correlation_id=correlation_id, depth=depth)

    transaction.on_commit(dispatch)
    return correlation_id


def execute_automation(*, automation, event_key, organization, actor, payload, correlation_id, depth):
    key = f"{automation.pk}:{event_key}:{correlation_id}"
    if depth >= MAX_AUTOMATION_DEPTH or automation.action_key not in ALLOWED_ACTIONS:
        return AutomationExecution.objects.get_or_create(automation=automation, organization=organization, event_key=event_key, correlation_id=correlation_id, depth=depth, status=AutomationExecution.Status.SKIPPED, result_summary="Automation depth or action policy blocked execution.", idempotency_key=key)[0]
    try:
        execution, created = AutomationExecution.objects.get_or_create(automation=automation, organization=organization, event_key=event_key, correlation_id=correlation_id, depth=depth, status=AutomationExecution.Status.EXECUTED, result_summary="", idempotency_key=key)
        if not created:
            return execution
        recipients = list(Membership.objects.active().filter(organization=organization).select_related("user").values_list("user", flat=True))
        if automation.action_key in {"notify.team", "notify.assignee", "notify.approver"} and recipients:
            create_notification(organization=organization, notification_type="automation.executed", category="team", title=automation.name, message=f"Automation: {event_key}", users=recipients, actor=actor)
        elif automation.action_key in {"callsheet.create_draft", "task.create"}:
            execution.result_summary = "Allowlisted action recorded for domain service integration."
            execution.save(update_fields=["result_summary", "updated_at"])
        automation.last_run_at = timezone.now()
        automation.save(update_fields=["last_run_at", "updated_at"])
        record_event(actor=actor, organization=organization, action="automation.executed", resource=automation, description=f"Executed automation {automation.name}.")
        return execution
    except (IntegrityError, Exception) as exc:
        execution, _ = AutomationExecution.objects.get_or_create(automation=automation, organization=organization, event_key=event_key, correlation_id=correlation_id, depth=depth, status=AutomationExecution.Status.FAILED, result_summary=str(exc)[:500], idempotency_key=key)
        return execution
