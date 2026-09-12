from datetime import date

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking
from notifications.selectors import inbox, unread_count
from organizations.selectors import organizations_for_user
from tasks.models import Task
from tasks.selectors import tasks_for_user

from ..models import ActionRequest, AIProviderConfig, Automation
from ..services import execute_action, propose_action


def organization_for(request):
    return get_object_or_404(organizations_for_user(request.user), pk=request.data.get("organization_id") or request.query_params.get("organization_id"))


class ActionSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    channel = serializers.CharField(max_length=32, default="copilot")
    action_key = serializers.CharField(max_length=80)
    payload = serializers.JSONField(default=dict)
    idempotency_key = serializers.CharField(max_length=160)


class ActionProposeView(APIView):
    def post(self, request):
        serializer = ActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = get_object_or_404(organizations_for_user(request.user), pk=serializer.validated_data["organization_id"])
        try:
            action = propose_action(actor=request.user, organization=organization, **serializer.validated_data)
        except (ValueError, PermissionError, IntegrityError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"id": action.id, "status": action.status, "risk": action.risk, "action_key": action.action_key, "confirmation_hash": action.confirmation_hash, "expires_at": action.expires_at, "result_summary": action.result_summary}, status=201)


class ActionExecuteView(APIView):
    def post(self, request, action_id):
        try:
            action = execute_action(action_request_id=action_id, actor=request.user, confirmation_hash=request.data.get("confirmation_hash"))
        except (ActionRequest.DoesNotExist, ValueError, PermissionError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"id": action.id, "status": action.status, "result_summary": action.result_summary})


class CopilotView(APIView):
    def post(self, request):
        prompt = str(request.data.get("message", "")).strip()
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.data.get("organization_id"))
        lowered = prompt.lower()
        if any(term in lowered for term in ("superuser", "api key", "run sql", "delete all", "record a payment", "royalty ownership", "change role")):
            return Response({"status": "blocked", "message": "I can’t perform that action. High-risk administration must be completed inside Evolve."})
        if "overdue" in lowered and "task" in lowered:
            data = list(tasks_for_user(request.user).filter(organization=organization).exclude(status__in=[Task.Status.DONE, Task.Status.CANCELLED], due_at__lt=__import__("django.utils.timezone", fromlist=["now"]).now()).values("id", "title", "due_at")[:50])
            return Response({"status": "answered", "message": f"You have {len(data)} overdue task(s).", "data": data})
        if "today" in lowered or "happening" in lowered:
            tasks = tasks_for_user(request.user).filter(organization=organization).exclude(status__in=[Task.Status.DONE, Task.Status.CANCELLED]).filter(due_at__date=date.today())
            bookings = Booking.objects.filter(organization=organization, event_date=date.today()).values("id", "title", "event_date")[:50]
            return Response({"status": "answered", "message": "Here is what is scheduled today.", "data": {"tasks": list(tasks.values("id", "title", "status")), "bookings": list(bookings)}})
        return Response({"status": "not_configured", "message": "AI Copilot is not configured. You can still use real Evolve workspace actions below."})


class MyWorkView(APIView):
    def get(self, request):
        qs = tasks_for_user(request.user).filter(assigned_membership__user=request.user).exclude(status=Task.Status.CANCELLED)
        return Response({"tasks": [{"id": t.id, "title": t.title, "status": t.status, "due_at": t.due_at, "overdue": t.is_overdue} for t in qs[:100]], "overdue": qs.filter(due_at__lt=__import__("django.utils.timezone", fromlist=["now"]).now()).exclude(status=Task.Status.DONE).count(), "notifications": unread_count(request.user)})


class WorkspaceInboxView(APIView):
    def get(self, request):
        notifications = inbox(request.user)[:50]
        actions = ActionRequest.objects.filter(actor=request.user, status=ActionRequest.Status.PROPOSED).order_by("expires_at")[:50]
        return Response({"notifications": [{"id": item.notification_id, "title": item.notification.title, "message": item.notification.message, "read_at": item.read_at, "action_url": item.notification.action_url} for item in notifications], "ai_confirmations": [{"id": item.id, "action_key": item.action_key, "risk": item.risk, "expires_at": item.expires_at} for item in actions]})


class AutomationListView(APIView):
    def get(self, request):
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.query_params.get("organization_id"))
        return Response(list(Automation.objects.filter(organization=organization).values("id", "name", "event_key", "action_key", "is_active", "last_run_at")))

    def post(self, request):
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.data.get("organization_id"))
        allowed_events = {"task.assigned", "booking.created", "callsheet.published", "contract.approval_requested"}
        allowed_actions = {"notify.assignee", "callsheet.create_draft", "notify.team", "notify.approver"}
        if request.data.get("event_key") not in allowed_events or request.data.get("action_key") not in allowed_actions:
            raise ValidationError("Automation event or action is not allowlisted.")
        item = Automation.objects.create(organization=organization, created_by=request.user, name=request.data.get("name", "Untitled automation"), event_key=request.data["event_key"], action_key=request.data["action_key"], condition=request.data.get("condition", {}), action_config=request.data.get("action_config", {}), is_active=False)
        return Response({"id": item.id, "status": "inactive"}, status=201)


class PlatformAIView(APIView):
    def get(self, request):
        if not request.user.is_superuser:
            return Response({"detail": "Not found."}, status=404)
        item = AIProviderConfig.objects.order_by("-created_at").first()
        return Response({"status": item.status if item else "not_configured", "provider": item.provider_name if item else None, "model": item.model if item else None, "secret_configured": bool(item and item.secret_reference)})
