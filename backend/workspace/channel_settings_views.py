from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.selectors import organizations_for_user

from .channel_models import MessagingConnector, MessagingIdentity


class ChannelSettingsView(APIView):
    def get(self, request):
        if request.user.is_superuser and request.query_params.get("platform") == "true":
            connectors = MessagingConnector.objects.all()
        else:
            connectors = MessagingConnector.objects.filter(organization__in=organizations_for_user(request.user))
        identities = MessagingIdentity.objects.filter(user=request.user).select_related("connector", "organization")
        return Response({"connectors": [{"id": item.id, "provider": item.provider_type, "name": item.name, "status": item.webhook_status, "active": item.is_active, "display_name": item.display_name, "display_phone": item.display_phone} for item in connectors], "identities": [{"id": item.id, "provider": item.connector.provider_type, "organization": item.organization.name, "active": item.is_active, "revoked": item.revoked_at is not None} for item in identities]})
