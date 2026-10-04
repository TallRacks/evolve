import hashlib
import hmac
import json
import os
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import record_event
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from signing.models import SigningEvent, SigningRequest
from signing.opensign import OpenSignUnavailable, create_signing_document

from .serializers import SigningEventResponseSerializer, SigningRequestSerializer


def scoped(request, pk):
    row = get_object_or_404(SigningRequest, pk=pk)
    if row.organization not in organizations_for_user(request.user):
        raise PermissionDenied("Signing request is outside your organization.")
    return row


class SigningRequestListView(APIView):
    def get(self, request):
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.query_params.get("organization_id"))
        if not user_has_organization_permission(request.user, organization, "contract.view"):
            raise PermissionDenied("Signing access required.")
        rows = SigningRequest.objects.filter(organization=organization)
        return Response(SigningRequestSerializer(rows, many=True).data)

    def post(self, request):
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.data.get("organization_id"))
        if not user_has_organization_permission(request.user, organization, "contract.signature.manage"):
            raise PermissionDenied("Signing management permission required.")
        serializer = SigningRequestSerializer(
            data=request.data, context={"organization": organization}
        )
        serializer.is_valid(raise_exception=True)
        row = serializer.save(organization=organization, created_by=request.user)
        if row.booking_id:
            if not row.source_document_id:
                linked_document = row.booking.document_links.select_related("document").order_by("-created_at").first()
                if linked_document:
                    row.source_document = linked_document.document
            if not row.source_contract_id:
                linked_contract = row.booking.contracts.order_by("-updated_at").first()
                if linked_contract:
                    row.source_contract = linked_contract
            row.save(update_fields=("source_document", "source_contract", "updated_at"))
        record_event(actor=request.user, organization=organization, action="signing.request_created", resource=row, description="Signing request created.", request=request)
        return Response(SigningRequestSerializer(row).data, status=201)


class SigningRequestDetailView(APIView):
    def get(self, request, request_id):
        row = scoped(request, request_id)
        if not user_has_organization_permission(request.user, row.organization, "contract.view"):
            raise PermissionDenied("Signing access required.")
        return Response({**SigningRequestSerializer(row).data, 'events': SigningEventResponseSerializer(row.events.all()[:25], many=True).data})


class SigningRequestActionView(APIView):
    """Perform local lifecycle steps; provider sending remains OpenSign-controlled."""

    def post(self, request, request_id):
        row = scoped(request, request_id)
        if not user_has_organization_permission(request.user, row.organization, "contract.signature.manage"):
            raise PermissionDenied("Signing management permission required.")
        action = str(request.data.get("action", "")).strip().lower()
        transitions = {
            "ready": ((SigningRequest.Status.DRAFT,), SigningRequest.Status.READY, "signing.request_ready"),
            "send": ((SigningRequest.Status.READY,), SigningRequest.Status.SENT, "signing.request_sent"),
            "cancel": ((SigningRequest.Status.DRAFT, SigningRequest.Status.READY), SigningRequest.Status.CANCELLED, "signing.request_cancelled"),
        }
        if action not in transitions:
            return Response({"detail": "Supported actions are ready, send, and cancel."}, status=400)
        allowed, target, audit_action = transitions[action]
        if row.status not in allowed:
            return Response({"detail": f"Cannot {action} a request in {row.status} status."}, status=409)
        if action == "send":
            if not row.source_document_id and row.source_contract_id:
                linked_document = (
                    row.source_contract.document_links.select_related("document")
                    .order_by("-created_at")
                    .first()
                )
                if linked_document:
                    row.source_document = linked_document.document
            try:
                created = create_signing_document(row)
            except OpenSignUnavailable as error:
                return Response({"detail": str(error)}, status=503)
            row.provider_document_id = created.provider_document_id
            row.signing_url = created.signing_url
        row.status = target
        row.last_event_at = timezone.now()
        row.save(update_fields=("source_document", "status", "last_event_at", "updated_at", "provider_document_id", "signing_url"))
        SigningEvent.objects.create(
            request=row,
            provider_event_id=f"evolve-{row.id}-{action}-{timezone.now().timestamp()}",
            event_type=action,
            status=target,
            payload_digest=hashlib.sha256(f"{row.id}:{action}:{target}".encode()).hexdigest(),
        )
        record_event(actor=request.user, organization=row.organization, action=audit_action, resource=row, description=f"Signing request marked {target}.", request=request)
        return Response(SigningRequestSerializer(row).data)


class SigningEventListView(APIView):
    def get(self, request, request_id):
        row = scoped(request, request_id)
        if not user_has_organization_permission(request.user, row.organization, "contract.view"):
            raise PermissionDenied('Signing access required.')
        return Response(SigningEventResponseSerializer(row.events.all()[:50], many=True).data)


STATUS_BY_EVENT = {
    "sent": SigningRequest.Status.SENT,
    "send": SigningRequest.Status.SENT,
    "delivered": SigningRequest.Status.SENT,
    "opened": SigningRequest.Status.VIEWED,
    "viewed": SigningRequest.Status.VIEWED,
    "accessed": SigningRequest.Status.VIEWED,
    "partially_signed": SigningRequest.Status.PARTIALLY_SIGNED,
    "partial_signed": SigningRequest.Status.PARTIALLY_SIGNED,
    "in_progress": SigningRequest.Status.PARTIALLY_SIGNED,
    "signed": SigningRequest.Status.COMPLETED,
    "completed": SigningRequest.Status.COMPLETED,
    "signing_completed": SigningRequest.Status.COMPLETED,
    "document_completed": SigningRequest.Status.COMPLETED,
    "declined": SigningRequest.Status.DECLINED,
    "rejected": SigningRequest.Status.DECLINED,
    "expired": SigningRequest.Status.EXPIRED,
    "cancelled": SigningRequest.Status.CANCELLED,
    "canceled": SigningRequest.Status.CANCELLED,
    "failed": SigningRequest.Status.FAILED,
    "signing_failed": SigningRequest.Status.FAILED,
    "error": SigningRequest.Status.FAILED,
}


def _nested(payload, *paths):
    for path in paths:
        value = payload
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if value not in (None, ""):
            return value
    return ""


def _normalise_opensign_event(payload):
    event_type = str(
        _nested(payload, ("event_type",), ("event",), ("type",), ("name",), ("data", "event"))
        or "provider_event"
    ).strip().lower().replace(" ", "_").replace("-", "_")
    raw_status = str(
        _nested(payload, ("status",), ("data", "status"), ("document", "status"))
        or event_type
    ).strip().lower().replace(" ", "_").replace("-", "_")
    status = STATUS_BY_EVENT.get(raw_status) or STATUS_BY_EVENT.get(event_type)
    if not status:
        raise ValueError("Unsupported OpenSign event status.")
    provider_id = str(
        _nested(
            payload,
            ("provider_document_id",),
            ("document_id",),
            ("documentId",),
            ("data", "document_id"),
            ("data", "documentId"),
            ("document", "objectId"),
            ("document", "id"),
        )
    )
    event_id = str(
        _nested(payload, ("event_id",), ("eventId",), ("id",), ("objectId",), ("data", "eventId"))
    )
    completed_url = str(
        _nested(
            payload,
            ("completed_document_url",),
            ("completedDocumentUrl",),
            ("data", "completed_document_url"),
            ("document", "completedDocumentUrl"),
        )
    )
    return {
        "event_id": event_id,
        "event_type": event_type,
        "status": status,
        "provider_document_id": provider_id,
        "completed_document_url": completed_url,
        "signers": payload.get("signers") or _nested(payload, ("data", "signers"), ("document", "signers")) or None,
    }


def _verify_webhook(request):
    secret = os.environ.get("EVOLVE_OPENSIGN_WEBHOOK_SECRET", "")
    signature = request.headers.get("X-Evolve-OpenSign-Signature", "") or request.headers.get("X-OpenSign-Signature", "")
    expected = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest() if secret else ""
    return bool(secret and signature and hmac.compare_digest(signature, expected))


def _apply_opensign_event(payload, request_id=None, request=None):
    event = _normalise_opensign_event(payload)
    lookup = {"provider": "opensign"}
    if request_id:
        lookup["pk"] = request_id
    elif event["provider_document_id"]:
        lookup["provider_document_id"] = event["provider_document_id"]
    else:
        raise ValueError("The webhook must include a request UUID or provider document ID.")
    with transaction.atomic():
        row = get_object_or_404(SigningRequest.objects.select_for_update(), **lookup)
        provider_event_id = event["event_id"] or hashlib.sha256(request.body if request else json.dumps(payload, sort_keys=True).encode()).hexdigest()
        digest = hashlib.sha256(request.body if request else json.dumps(payload, sort_keys=True).encode()).hexdigest()
        signing_event, created = SigningEvent.objects.get_or_create(
            request=row,
            provider_event_id=provider_event_id,
            defaults={"event_type": event["event_type"], "status": event["status"], "payload_digest": digest},
        )
        if not created:
            return row, False
        terminal = {
            SigningRequest.Status.COMPLETED,
            SigningRequest.Status.DECLINED,
            SigningRequest.Status.EXPIRED,
            SigningRequest.Status.CANCELLED,
        }
        updates = {"last_event_at": timezone.now()}
        if row.status not in terminal:
            updates["status"] = event["status"]
        if event["provider_document_id"] and not row.provider_document_id:
            updates["provider_document_id"] = event["provider_document_id"]
        if event["completed_document_url"]:
            updates["completed_document_url"] = event["completed_document_url"]
        if event["signers"] is not None:
            updates["signers"] = event["signers"]
        SigningRequest.objects.filter(pk=row.pk).update(**updates)
        row.refresh_from_db()
        record_event(
            actor=None,
            organization=row.organization,
            action="signing.provider_event",
            resource=row,
            description=f"OpenSign reported {event['event_type']} ({event['status']}).",
            request=request,
        )
        return row, True


class OpenSignWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, request_id=None):
        if not _verify_webhook(request):
            return Response({"detail": "Invalid webhook signature."}, status=403)
        if not isinstance(request.data, dict):
            return Response({"detail": "Webhook body must be a JSON object."}, status=400)
        try:
            row, created = _apply_opensign_event(request.data, request_id=request_id, request=request)
        except ValueError as error:
            return Response({"detail": str(error)}, status=400)
        return Response({"status": "accepted", "duplicate": not created, "request_id": str(row.id)})
