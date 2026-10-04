from django.shortcuts import get_object_or_404
from django.db.models import Q
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
        actor = request.query_params.get("actor", "").strip()
        action = request.query_params.get("action", "").strip()
        resource_type = request.query_params.get("resource_type", "").strip()
        organization = request.query_params.get("organization", "").strip()
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        events = AuditEvent.objects.select_related("actor", "organization")
        if actor:
            events = events.filter(Q(actor__email__icontains=actor))
        if action: events = events.filter(action__icontains=action)
        if resource_type: events = events.filter(resource_type__icontains=resource_type)
        if organization: events = events.filter(Q(organization__name__icontains=organization) | Q(organization_id=organization))
        if date_from: events = events.filter(created_at__date__gte=date_from)
        if date_to: events = events.filter(created_at__date__lte=date_to)
        rows = [{
            "id": str(event.id), "created_at": event.created_at,
            "actor": event.actor.email if event.actor else None,
            "organization": event.organization.name if event.organization else None,
            "action": event.action, "resource_type": event.resource_type,
            "resource_id": event.resource_id, "description": event.description,
            "ip_address": event.ip_address, "kind": "audit",
        } for event in events[:300]]
        from notifications.models import EmailDeliveryAttempt, Notification
        notifications = Notification.objects.select_related("actor", "organization")
        deliveries = EmailDeliveryAttempt.objects.select_related("user", "organization")
        if actor:
            notifications = notifications.filter(Q(actor__email__icontains=actor))
            deliveries = deliveries.filter(Q(user__email__icontains=actor))
        if organization:
            notifications = notifications.filter(Q(organization__name__icontains=organization) | Q(organization_id=organization))
            deliveries = deliveries.filter(Q(organization__name__icontains=organization) | Q(organization_id=organization))
        if date_from:
            notifications = notifications.filter(created_at__date__gte=date_from)
            deliveries = deliveries.filter(attempted_at__date__gte=date_from)
        if date_to:
            notifications = notifications.filter(created_at__date__lte=date_to)
            deliveries = deliveries.filter(attempted_at__date__lte=date_to)
        if not action or "notification" in action:
            rows.extend({
                "id": f"notification:{item.id}", "created_at": item.created_at,
                "actor": item.actor.email if item.actor else None,
                "organization": item.organization.name if item.organization else None,
                "action": "notification.created", "resource_type": "Notification",
                "resource_id": str(item.id), "description": f"{item.title}: {item.message}",
                "ip_address": None, "kind": "notification",
            } for item in notifications[:300])
        if not action or "email" in action or "mail" in action:
            rows.extend({
                "id": f"email:{item.id}", "created_at": item.attempted_at,
                "actor": item.user.email if item.user else None,
                "organization": item.organization.name if item.organization else None,
                "action": f"email.delivery.{item.status}", "resource_type": "EmailDeliveryAttempt",
                "resource_id": str(item.id), "description": f"{item.template_key} sent to {item.recipient_email_snapshot}",
                "ip_address": None, "kind": "email",
            } for item in deliveries[:300])
        rows.sort(key=lambda item: item["created_at"], reverse=True)
        return Response(rows[:500])
