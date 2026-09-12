import json

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .channel_models import ChannelVerification, InboundMessage, MessagingConnector, MessagingIdentity
from .channel_services import accept_inbound, command_result, resolve_identity, verification_code, verify_signature
from organizations.selectors import organizations_for_user


MAX_BODY = 256 * 1024


def parse_request(request):
    if request.method != "POST" or request.content_type != "application/json" or len(request.body) > MAX_BODY:
        return None
    try:
        value = json.loads(request.body)
    except (TypeError, ValueError):
        return None
    if not isinstance(value, dict) or not value.get("provider_message_id") or not value.get("sender_subject"):
        return None
    return value


class WhatsAppWebhookView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, connector_id):
        connector = get_object_or_404(MessagingConnector, pk=connector_id, provider_type=MessagingConnector.Provider.WHATSAPP)
        token = request.query_params.get("hub.verify_token", "")
        expected = __import__("os").environ.get(connector.verification_token_reference, "")
        if not expected or not hmac_compare(token, expected):
            return Response({"detail": "Invalid verification."}, status=status.HTTP_403_FORBIDDEN)
        return HttpResponse(request.query_params.get("hub.challenge", ""), content_type="text/plain")

    def post(self, request, connector_id):
        connector = get_object_or_404(MessagingConnector, pk=connector_id, provider_type=MessagingConnector.Provider.WHATSAPP)
        if not verify_signature(connector=connector, body=request.body, signature=request.headers.get("X-Evolve-Signature", "")):
            return Response({"detail": "Invalid signature."}, status=status.HTTP_403_FORBIDDEN)
        payload = parse_request(request)
        if payload is None:
            return Response({"detail": "Invalid webhook."}, status=status.HTTP_400_BAD_REQUEST)
        identity = resolve_identity(connector=connector, provider_subject=str(payload["sender_subject"]), code=payload.get("verification_code"))
        message, created = accept_inbound(connector=connector, payload=payload, identity=identity)
        if not created:
            return Response({"status": "duplicate"})
        if not identity or not identity.is_active:
            return Response({"status": "accepted", "message": "Identity not linked."})
        return Response({"status": "accepted", "result": command_result(identity=identity, organization=identity.active_context, text=message.body_text)})


class InboundEmailWebhookView(WhatsAppWebhookView):
    def post(self, request, connector_id):
        connector = get_object_or_404(MessagingConnector, pk=connector_id, provider_type=MessagingConnector.Provider.EMAIL)
        if not verify_signature(connector=connector, body=request.body, signature=request.headers.get("X-Evolve-Signature", "")):
            return Response({"detail": "Invalid signature."}, status=status.HTTP_403_FORBIDDEN)
        payload = parse_request(request)
        if payload is None:
            return Response({"detail": "Invalid webhook."}, status=status.HTTP_400_BAD_REQUEST)
        identity = resolve_identity(connector=connector, provider_subject=str(payload["sender_subject"]))
        message, created = accept_inbound(connector=connector, payload=payload, identity=identity)
        if not created:
            return Response({"status": "duplicate"})
        if message.has_attachments:
            return Response({"status": "accepted", "message": "Attachments cannot yet be processed through email automation. Upload the file securely in Evolve."})
        if not identity or not identity.is_active:
            return Response({"status": "accepted", "message": "Sender is not linked to an active Evolve identity."})
        return Response({"status": "accepted", "result": command_result(identity=identity, organization=identity.active_context, text=message.body_text)})


def hmac_compare(left, right):
    import hmac
    return hmac.compare_digest(left.encode(), right.encode())


class ChannelConnectView(APIView):
    def post(self, request):
        connector = get_object_or_404(MessagingConnector, pk=request.data.get("connector_id"), provider_type=MessagingConnector.Provider.WHATSAPP, is_active=True)
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.data.get("organization_id"))
        return Response({"code": verification_code(user=request.user, organization=organization, connector=connector, channel="whatsapp"), "expires_in": 600})


class ChannelDisconnectView(APIView):
    def post(self, request, identity_id):
        identity = get_object_or_404(MessagingIdentity, pk=identity_id, user=request.user)
        identity.revoked_at = __import__("django.utils.timezone", fromlist=["now"]).now()
        identity.save(update_fields=["revoked_at", "updated_at"])
        return Response({"status": "revoked"})
