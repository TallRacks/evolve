import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from tasks.models import Task
from tasks.selectors import tasks_for_user

from .channel_models import ChannelVerification, InboundMessage, MessagingConnector, MessagingIdentity
from .services import propose_action


def verify_signature(*, connector, body, signature):
    secret = os.environ.get(connector.signing_secret_reference, "")
    if not secret or not signature:
        return False
    supplied = signature.removeprefix("sha256=")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)


def verification_code(*, user, organization, connector, channel):
    code = secrets.token_urlsafe(6).upper().replace("-", "").replace("_", "")[:8]
    ChannelVerification.objects.filter(user=user, connector=connector, used_at__isnull=True).update(used_at=timezone.now())
    item = ChannelVerification(user=user, organization=organization, connector=connector, channel=channel, code_hash=hashlib.sha256(code.encode()).hexdigest(), expires_at=timezone.now() + timedelta(minutes=10))
    item.save()
    return code


@transaction.atomic
def resolve_identity(*, connector, provider_subject, code=None):
    identity = MessagingIdentity.objects.select_for_update().select_related("user", "connector").filter(connector=connector, provider_subject=provider_subject, is_verified=True, revoked_at__isnull=True).first()
    if identity:
        return identity
    if not code:
        return None
    digest = hashlib.sha256(code.upper().encode()).hexdigest()
    verification = ChannelVerification.objects.select_for_update().filter(connector=connector, code_hash=digest, provider_subject="", used_at__isnull=True).order_by("-created_at").first()
    if not verification or not verification.usable:
        return None
    verification.provider_subject = provider_subject
    verification.used_at = timezone.now()
    verification.save(update_fields=["provider_subject", "used_at", "updated_at"])
    identity = MessagingIdentity.objects.create(connector=connector, user=verification.user, organization=verification.organization, provider_subject=provider_subject, display_address=provider_subject, is_verified=True, active_context=verification.organization)
    return identity


def authorized_context(identity, requested_organization=None):
    orgs = organizations_for_user(identity.user)
    if requested_organization:
        return orgs.filter(pk=requested_organization).first()
    if identity.active_context_id and orgs.filter(pk=identity.active_context_id).exists():
        return identity.active_context
    return orgs.get() if orgs.count() == 1 else None


def command_result(*, identity, organization, text):
    lowered = text.lower().strip()
    if lowered in {"current workspace", "workspace"}:
        return {"kind": "workspaces", "workspaces": list(organizations_for_user(identity.user).values("id", "name"))}
    if lowered.startswith("switch workspace "):
        candidate = lowered.removeprefix("switch workspace ").strip()
        org = organizations_for_user(identity.user).filter(slug=candidate).first()
        if not org:
            return {"kind": "error", "message": "I could not find an accessible workspace."}
        identity.active_context = org
        identity.save(update_fields=["active_context", "updated_at"])
        return {"kind": "workspace", "message": f"Current workspace: {org.name}."}
    if not organization:
        return {"kind": "context_required", "message": "Choose a workspace first: reply CURRENT WORKSPACE."}
    if "my tasks" in lowered or "due today" in lowered:
        rows = tasks_for_user(identity.user).filter(organization=organization).exclude(status__in=[Task.Status.DONE, Task.Status.CANCELLED])[:25]
        return {"kind": "tasks", "organization": organization.name, "tasks": list(rows.values("id", "title", "status", "due_at"))}
    return {"kind": "not_configured", "message": "This channel can answer supported Evolve queries and propose approved actions. Try MY TASKS or CURRENT WORKSPACE."}


def accept_inbound(*, connector, payload, identity=None):
    provider_id = str(payload["provider_message_id"])
    message, created = InboundMessage.objects.get_or_create(connector=connector, provider_message_id=provider_id, defaults={"channel": connector.provider_type, "sender_address": str(payload["sender_subject"]), "event_type": str(payload.get("event_type", "message")), "body_text": str(payload.get("text", ""))[:10000], "subject": str(payload.get("subject", ""))[:220], "has_attachments": bool(payload.get("has_attachments", False)), "identity": identity, "organization": identity.organization if identity and identity.is_active else None})
    return message, created
