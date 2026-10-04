from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking
from campaigns.models import Campaign, Rollout
from contracts.models import ContractApproval
from contracts.selectors import contracts_for_user
from contracts.services import decide_approval
from music.models import Release
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from production.models import ProductionAdvance
from tasks.models import Task
from tasks.selectors import tasks_for_user


def org(request):
    return get_object_or_404(
        organizations_for_user(request.user), pk=request.query_params.get("organization_id")
    )


class ApprovalHubView(APIView):
    def get(self, request):
        organization = org(request)
        rows = ContractApproval.objects.filter(contract__organization=organization).select_related(
            "contract", "contract__artist", "membership__user"
        )
        view = request.query_params.get("view", "pending")
        if view == "pending":
            rows = rows.filter(status="pending", membership__user=request.user)
        elif view == "requested":
            rows = rows.filter(contract__created_by=request.user)
        else:
            rows = rows.exclude(status="pending")
        return Response(
            [
                {
                    "id": row.id,
                    "contract": row.contract_id,
                    "reference": row.contract.reference,
                    "title": row.contract.title,
                    "artist": row.contract.artist.stage_name if row.contract.artist else None,
                    "requested_by": row.contract.created_by.email
                    if row.contract.created_by
                    else None,
                    "approver": row.membership.user.email,
                    "status": row.status,
                    "requested_at": row.created_at,
                }
                for row in rows[:100]
            ]
        )

    def post(self, request):
        row = get_object_or_404(
            ContractApproval.objects.select_related("contract__organization", "membership__user"),
            pk=request.data.get("approval_id"),
            contract__in=contracts_for_user(request.user),
        )
        serializer = serializers.Serializer(data=request.data)
        serializer.fields["decision"] = serializers.ChoiceField(
            choices=["approved", "rejected", "cancelled"]
        )
        serializer.is_valid(raise_exception=True)
        result = decide_approval(
            row,
            actor=request.user,
            decision=serializer.validated_data["decision"],
            comment=request.data.get("comment", ""),
        )
        return Response({"id": result.id, "status": result.status})


class BoardView(APIView):
    def get(self, request, board_key):
        organization = org(request)
        if board_key == "tasks":
            if not user_has_organization_permission(request.user, organization, "task.view"):
                return Response({"detail": "Forbidden."}, status=403)
            rows = (
                tasks_for_user(request.user)
                .filter(organization=organization)
                .select_related("assigned_membership__user")
            )
            if request.query_params.get("workspace_id"):
                rows = rows.filter(source_document__workspace_id=request.query_params["workspace_id"])
            rows = rows[:200]
            cards = [
                {
                    "id": row.id,
                    "title": row.title,
                    "status": row.status,
                    "priority": row.priority,
                    "assignee": f"{assigned_membership.user.first_name} {assigned_membership.user.last_name}".strip()
                    if row.assigned_membership
                    else None,
                    "due_at": row.due_at,
                    "progress": row.progress,
                }
                for row in rows
            ]
            columns = ["todo", "in_progress", "blocked", "done"]
        elif board_key == "bookings":
            rows = Booking.objects.filter(organization=organization).select_related(
                "artist", "venue"
            )[:200]
            cards = [
                {
                    "id": row.id,
                    "reference": row.reference,
                    "title": row.title,
                    "status": row.status,
                    "artist": row.artist.stage_name,
                    "event_date": row.event_date,
                    "venue": row.venue.name if row.venue else None,
                    "priority": row.priority,
                }
                for row in rows
            ]
            columns = sorted({row["status"] for row in cards})
        elif board_key == "production":
            rows = ProductionAdvance.objects.filter(organization=organization).select_related(
                "booking", "artist"
            )[:200]
            cards = [
                {
                    "id": row.id,
                    "title": row.production_title,
                    "status": row.status,
                    "artist": row.artist.stage_name,
                    "booking": row.booking.reference,
                }
                for row in rows
            ]
            columns = sorted({row["status"] for row in cards})
        elif board_key == "campaigns":
            rows = Campaign.objects.filter(organization=organization).select_related("artist")[:200]
            cards = [
                {
                    "id": row.id,
                    "title": row.name,
                    "status": row.status,
                    "artist": row.artist.stage_name,
                    "priority": row.priority,
                }
                for row in rows
            ]
            columns = sorted({row["status"] for row in cards})
        elif board_key == "releases":
            rows = Release.objects.filter(organization=organization).select_related(
                "primary_artist"
            )[:200]
            cards = [
                {
                    "id": row.id,
                    "title": row.title,
                    "status": row.status,
                    "artist": row.primary_artist.stage_name,
                    "planned_release_date": row.planned_release_date,
                }
                for row in rows
            ]
            columns = sorted({row["status"] for row in cards})
        else:
            return Response({"detail": "Unsupported board."}, status=404)
        return Response(
            {"board": board_key, "columns": columns, "cards": cards, "list_supported": True}
        )


BOARD_FIELD_REGISTRY = {
    "tasks": ("status", "assignee", "priority", "due_date", "context"),
    "bookings": ("artist", "date", "venue", "priority", "readiness", "owner"),
    "production": ("status", "artist", "booking"),
    "campaign_rollout": ("status", "artist", "priority"),
    "releases": ("artist", "release_date", "readiness", "campaign", "status"),
}
