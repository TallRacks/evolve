from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.api.permissions import PlatformSuperuser

from ..models import AuditEvent


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
