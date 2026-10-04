from datetime import date

from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from audit.services import record_event
from organizations.permissions import user_has_organization_permission
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking
from notifications.selectors import inbox, unread_count
from organizations.selectors import organizations_for_user
from tasks.models import Task
from tasks.selectors import tasks_for_user

from ..models import ActionRequest, AIProviderConfig, Automation, Board, Workspace
from ..domain_views import BOARD_FIELD_REGISTRY
from ..summary_services import booking_summary, daily_summary, release_summary, workspace_summary
from ..services import execute_action, propose_action
from ..ai_services import answer_with_model


def organization_for(request):
    return get_object_or_404(
        organizations_for_user(request.user),
        pk=request.data.get("organization_id") or request.query_params.get("organization_id"),
    )


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
        organization = get_object_or_404(
            organizations_for_user(request.user), pk=serializer.validated_data["organization_id"]
        )
        try:
            action = propose_action(
                actor=request.user, organization=organization, **serializer.validated_data
            )
        except (ValueError, PermissionError, IntegrityError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            {
                "id": action.id,
                "status": action.status,
                "risk": action.risk,
                "action_key": action.action_key,
                "confirmation_hash": action.confirmation_hash,
                "expires_at": action.expires_at,
                "result_summary": action.result_summary,
            },
            status=201,
        )


class ActionExecuteView(APIView):
    def post(self, request, action_id):
        try:
            action = execute_action(
                action_request_id=action_id,
                actor=request.user,
                confirmation_hash=request.data.get("confirmation_hash"),
                channel=request.data.get("channel"),
            )
        except (ActionRequest.DoesNotExist, ValueError, PermissionError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            {"id": action.id, "status": action.status, "result_summary": action.result_summary}
        )


class CopilotView(APIView):
    def post(self, request):
        prompt = str(request.data.get("message", "")).strip()
        organization = get_object_or_404(
            organizations_for_user(request.user), pk=request.data.get("organization_id")
        )
        lowered = prompt.lower()
        if any(
            term in lowered for term in ("summary", "briefing", "needs attention", "what is due")
        ):
            from ..summary_services import daily_summary

            return Response(
                {
                    "status": "answered",
                    "message": "Here is your deterministic Evolve summary.",
                    "data": daily_summary(user=request.user, organization=organization),
                }
            )
        if any(
            term in lowered
            for term in (
                "superuser",
                "api key",
                "run sql",
                "delete all",
                "record a payment",
                "royalty ownership",
                "change role",
            )
        ):
            return Response(
                {
                    "status": "blocked",
                    "message": "I can’t perform that action. High-risk administration must be completed inside Evolve.",
                }
            )
        if "overdue" in lowered and "task" in lowered:
            data = list(
                tasks_for_user(request.user)
                .filter(organization=organization)
                .filter(due_at__lt=__import__("django.utils.timezone", fromlist=["now"]).now())
                .exclude(status__in=[Task.Status.DONE, Task.Status.CANCELLED])
                .values("id", "title", "due_at")[:50]
            )
            return Response(
                {
                    "status": "answered",
                    "message": f"You have {len(data)} overdue task(s).",
                    "data": data,
                }
            )
        if "today" in lowered or "happening" in lowered:
            tasks = (
                tasks_for_user(request.user)
                .filter(organization=organization)
                .exclude(status__in=[Task.Status.DONE, Task.Status.CANCELLED])
                .filter(due_at__date=date.today())
            )
            bookings = Booking.objects.filter(
                organization=organization, event_date=date.today()
            ).values("id", "title", "event_date")[:50]
            return Response(
                {
                    "status": "answered",
                    "message": "Here is what is scheduled today.",
                    "data": {
                        "tasks": list(tasks.values("id", "title", "status")),
                        "bookings": list(bookings),
                    },
                }
            )
        model_answer = answer_with_model(
            prompt=prompt,
            organization=organization,
            user=request.user,
        )
        if model_answer:
            return Response(
                {
                    "status": "answered",
                    "message": model_answer,
                    "data": {"provider": "qwen3", "mode": "read_only"},
                }
            )
        return Response(
            {
                "status": "not_configured",
                "message": "AI Copilot is not configured. You can still use real Evolve workspace actions below.",
            }
        )


class MyWorkView(APIView):
    def get(self, request):
        organization = get_object_or_404(
            organizations_for_user(request.user),
            pk=request.query_params.get("organization_id"),
        )
        qs = (
            tasks_for_user(request.user)
            .filter(organization=organization)
            .filter(
                Q(assigned_membership__user=request.user)
                | Q(additional_assignees__user=request.user)
            )
            .distinct()
            .exclude(status=Task.Status.CANCELLED)
        )
        return Response(
            {
                "tasks": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "status": t.status,
                        "due_at": t.due_at,
                        "overdue": t.is_overdue,
                    }
                    for t in qs[:100]
                ],
                "overdue": qs.filter(
                    due_at__lt=__import__("django.utils.timezone", fromlist=["now"]).now()
                )
                .exclude(status=Task.Status.DONE)
                .count(),
                "notifications": unread_count(request.user),
            }
        )


class WorkspaceInboxView(APIView):
    def get(self, request):
        notifications = inbox(request.user)[:50]
        actions = ActionRequest.objects.filter(
            actor=request.user, status=ActionRequest.Status.PROPOSED
        ).order_by("expires_at")[:50]
        return Response(
            {
                "notifications": [
                    {
                        "id": item.notification_id,
                        "title": item.notification.title,
                        "message": item.notification.message,
                        "read_at": item.read_at,
                        "action_url": item.notification.action_url,
                    }
                    for item in notifications
                ],
                "ai_confirmations": [
                    {
                        "id": item.id,
                        "action_key": item.action_key,
                        "risk": item.risk,
                        "expires_at": item.expires_at,
                    }
                    for item in actions
                ],
            }
        )


class AutomationListView(APIView):
    def get(self, request):
        organization = get_object_or_404(
            organizations_for_user(request.user), pk=request.query_params.get("organization_id")
        )
        return Response(
            list(
                Automation.objects.filter(organization=organization).values(
                    "id", "name", "event_key", "action_key", "is_active", "last_run_at"
                )
            )
        )

    def post(self, request):
        organization = get_object_or_404(
            organizations_for_user(request.user), pk=request.data.get("organization_id")
        )
        allowed_events = {
            "task.assigned",
            "booking.created",
            "callsheet.published",
            "contract.approval_requested",
        }
        allowed_actions = {
            "notify.assignee",
            "callsheet.create_draft",
            "notify.team",
            "notify.approver",
        }
        if (
            request.data.get("event_key") not in allowed_events
            or request.data.get("action_key") not in allowed_actions
        ):
            raise ValidationError("Automation event or action is not allowlisted.")
        item = Automation.objects.create(
            organization=organization,
            created_by=request.user,
            name=request.data.get("name", "Untitled automation"),
            event_key=request.data["event_key"],
            action_key=request.data["action_key"],
            condition=request.data.get("condition", {}),
            action_config=request.data.get("action_config", {}),
            is_active=False,
        )
        return Response({"id": item.id, "status": "inactive"}, status=201)


class PlatformAIView(APIView):
    def get(self, request):
        if not request.user.is_superuser:
            return Response({"detail": "Not found."}, status=404)
        item = AIProviderConfig.objects.order_by("-created_at").first()
        return Response(
            {
                "status": item.status if item else "not_configured",
                "provider": item.provider_name if item else None,
                "model": item.model if item else None,
                "secret_configured": bool(item and item.secret_reference),
            }
        )


def workspace_for_request(request, workspace_id):
    return get_object_or_404(
        Workspace.objects.select_related("organization"),
        pk=workspace_id,
        organization__in=organizations_for_user(request.user),
    )


class WorkspaceListView(APIView):
    def get(self, request):
        organization = organization_for(request)
        rows = Workspace.objects.filter(organization=organization, archived=False)
        return Response(
            [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "slug": row.slug,
                    "description": row.description,
                    "icon": row.icon,
                }
                for row in rows
            ]
        )

    def post(self, request):
        organization = organization_for(request)
        if not user_has_organization_permission(request.user, organization, "organization.manage"):
            return Response({"detail": "Forbidden."}, status=403)
        row = Workspace.objects.create(
            organization=organization,
            created_by=request.user,
            name=str(request.data.get("name", "")).strip(),
            slug=str(request.data.get("slug", "")).strip(),
            description=request.data.get("description", ""),
            icon=request.data.get("icon", ""),
        )
        record_event(
            actor=request.user,
            organization=organization,
            action="workspace.created",
            resource=row,
            description="Created workspace.",
        )
        return Response({"id": str(row.id), "name": row.name, "slug": row.slug}, status=201)


class WorkspaceSummaryView(APIView):
    def get(self, request, workspace_id):
        return Response(
            workspace_summary(
                user=request.user, workspace=workspace_for_request(request, workspace_id)
            )
        )


class WorkspaceBoardView(APIView):
    def get(self, request, workspace_id):
        workspace = workspace_for_request(request, workspace_id)
        return Response(
            [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "source_type": row.source_type,
                    "default_view": row.default_view,
                    "allowed_fields": BOARD_FIELD_REGISTRY[row.source_type],
                }
                for row in workspace.boards.filter(archived=False)
            ]
        )

    def post(self, request, workspace_id):
        workspace = workspace_for_request(request, workspace_id)
        if workspace.archived:
            raise ValidationError("Archived Workspaces do not accept new Boards.")
        if not user_has_organization_permission(
            request.user, workspace.organization, "organization.manage"
        ):
            return Response({"detail": "Forbidden."}, status=403)
        source = request.data.get("source_type")
        if source not in BOARD_FIELD_REGISTRY:
            raise ValidationError("Unsupported board source.")
        row = Board.objects.create(
            workspace=workspace,
            created_by=request.user,
            name=str(request.data.get("name", "")).strip(),
            source_type=source,
            default_view=request.data.get("default_view", Board.View.LIST),
            description=request.data.get("description", ""),
        )
        record_event(
            actor=request.user,
            organization=workspace.organization,
            action="board.created",
            resource=row,
            description="Created workspace board.",
        )
        return Response(
            {
                "id": str(row.id),
                "name": row.name,
                "source_type": row.source_type,
                "default_view": row.default_view,
                "allowed_fields": BOARD_FIELD_REGISTRY[row.source_type],
            },
            status=201,
        )


class DailySummaryView(APIView):
    def get(self, request):
        organization = get_object_or_404(
            organizations_for_user(request.user), pk=request.query_params.get("organization_id")
        )

        return Response(daily_summary(user=request.user, organization=organization))


class WorkspaceDetailView(APIView):
    def get(self, request, workspace_id):
        workspace = workspace_for_request(request, workspace_id)
        return Response(
            {
                "id": str(workspace.id),
                "name": workspace.name,
                "slug": workspace.slug,
                "description": workspace.description,
                "icon": workspace.icon,
                "archived": workspace.archived,
            }
        )

    def patch(self, request, workspace_id):
        workspace = workspace_for_request(request, workspace_id)
        if not user_has_organization_permission(
            request.user, workspace.organization, "organization.manage"
        ):
            return Response({"detail": "Forbidden."}, status=403)
        for field in ("name", "slug", "description", "icon"):
            if field in request.data:
                setattr(workspace, field, str(request.data[field]).strip())
        if "archived" in request.data:
            workspace.archived = bool(request.data["archived"])
        workspace.save()
        record_event(
            actor=request.user,
            organization=workspace.organization,
            action="workspace.archived" if workspace.archived else "workspace.updated",
            resource=workspace,
            description="Updated workspace.",
        )
        return self.get(request, workspace_id)


class BoardDetailView(APIView):
    def patch(self, request, board_id):
        board = get_object_or_404(
            Board.objects.select_related("workspace__organization"),
            pk=board_id,
            workspace__organization__in=organizations_for_user(request.user),
        )
        if not user_has_organization_permission(
            request.user, board.workspace.organization, "organization.manage"
        ):
            return Response({"detail": "Forbidden."}, status=403)
        for field in ("name", "description", "default_view"):
            if field in request.data:
                setattr(board, field, str(request.data[field]))
        if request.data.get("archived") is True:
            board.archived = True
        board.save()
        record_event(
            actor=request.user,
            organization=board.workspace.organization,
            action="board.updated",
            resource=board,
            description="Updated workspace board.",
        )
        return Response(
            {
                "id": str(board.id),
                "name": board.name,
                "source_type": board.source_type,
                "default_view": board.default_view,
                "archived": board.archived,
                "allowed_fields": BOARD_FIELD_REGISTRY[board.source_type],
            }
        )

    def post(self, request, board_id, action):
        if action != "archive":
            raise ValidationError("Unsupported board action.")
        board = get_object_or_404(
            Board.objects.select_related("workspace__organization"),
            pk=board_id,
            workspace__organization__in=organizations_for_user(request.user),
        )
        if not user_has_organization_permission(
            request.user, board.workspace.organization, "organization.manage"
        ):
            return Response({"detail": "Forbidden."}, status=403)
        board.archived = True
        board.save(update_fields=("archived", "updated_at"))
        record_event(
            actor=request.user,
            organization=board.workspace.organization,
            action="board.updated",
            resource=board,
            description="Archived workspace board.",
        )
        return Response({"id": str(board.id), "archived": board.archived})
