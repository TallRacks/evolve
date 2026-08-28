from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.api.permissions import PlatformSuperuser
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from tasks.selectors import tasks_for_user

from ..models import AuditEvent

DOMAIN_PERMISSIONS = {
    "invoice": "finance.view",
    "payment": "finance.view",
    "finance": "finance.view",
    "rights": "rights.view",
    "royalty": "royalties.view",
    "contract": "contract.view",
    "travel": "travel.view",
    "production": "production.view",
    "booking": "booking.view",
    "callsheet": "callsheet.view",
    "call_sheet": "callsheet.view",
    "release": "music.view",
    "track": "music.view",
    "campaign": "campaign.view",
    "rollout": "rollout.view",
    "task": "task.view",
    "document": "document.view",
}

DESTINATIONS = {
    "Booking": "/workspace/bookings/{id}",
    "CallSheetVersion": "/workspace/call-sheets/{id}",
    "Release": "/workspace/music/releases/{id}",
    "Campaign": "/workspace/campaigns/{id}",
    "Task": "/workspace/tasks/{id}",
    "Contract": "/workspace/contracts/{id}",
    "TravelItinerary": "/workspace/travel/{id}",
    "ProductionAdvance": "/workspace/production/{id}",
    "Document": "/workspace/documents/{id}",
}


def event_permission(event):
    value = f"{event.action} {event.resource_type}".lower()
    return next(
        (permission for prefix, permission in DOMAIN_PERMISSIONS.items() if prefix in value),
        None,
    )


class WorkspaceActivityView(APIView):
    def get(self, request):
        organization = get_object_or_404(
            organizations_for_user(request.user),
            pk=request.query_params.get("organization_id"),
        )
        if not user_has_organization_permission(request.user, organization, "activity.view"):
            return Response(status=403)
        queryset = AuditEvent.objects.filter(organization=organization).select_related("actor")
        if request.query_params.get("domain"):
            queryset = queryset.filter(action__startswith=request.query_params["domain"] + ".")
        if request.query_params.get("actor"):
            queryset = queryset.filter(actor_id=request.query_params["actor"])
        if request.query_params.get("date_from"):
            queryset = queryset.filter(created_at__date__gte=request.query_params["date_from"])
        visible_task_ids = {
            str(value)
            for value in tasks_for_user(request.user)
            .filter(organization=organization)
            .values_list("pk", flat=True)
        }
        data = []
        for event in queryset[:250]:
            if event.resource_type == "Task" and event.resource_id not in visible_task_ids:
                continue
            permission = event_permission(event)
            if permission and not user_has_organization_permission(
                request.user, organization, permission
            ):
                continue
            destination = DESTINATIONS.get(event.resource_type)
            data.append(
                {
                    "id": event.pk,
                    "actor": event.actor.email if event.actor else "System",
                    "action": event.action,
                    "description": event.description,
                    "resource_type": event.resource_type,
                    "resource_id": event.resource_id,
                    "destination": destination.format(id=event.resource_id)
                    if destination
                    else None,
                    "created_at": event.created_at,
                }
            )
        return Response(data)


class PlatformAuditView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        events = AuditEvent.objects.select_related("actor", "organization")[:200]
        return Response(
            [
                {
                    "id": event.id,
                    "created_at": event.created_at,
                    "actor": event.actor.email if event.actor else None,
                    "organization": event.organization.name if event.organization else None,
                    "action": event.action,
                    "resource_type": event.resource_type,
                    "resource_id": event.resource_id,
                    "description": event.description,
                    "ip_address": event.ip_address,
                }
                for event in events
            ]
        )
