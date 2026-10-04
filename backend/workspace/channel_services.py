import hashlib
import hmac
import json
import os
import secrets
import uuid
from email import policy
from email.parser import BytesParser
from email.header import decode_header
from datetime import UTC, datetime, timedelta
import urllib.error
import urllib.request

from django.db import transaction
from django.utils import timezone

from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from tasks.models import Task
from tasks.selectors import tasks_for_user
from integrations.models import EmailConnector
from integrations.services import _google_oauth_access_token_for_email, _imap

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



def sync_imap_mailbox(*, connector, messaging_connector, organization, limit=50):
    if not isinstance(connector, EmailConnector) or connector.provider_type != "imap":
        return {"created": 0, "skipped": 0, "message": "No IMAP connector selected."}
    created = 0
    client = _imap(connector)
    try:
        status, data = client.select("INBOX", readonly=True)
        if status != "OK":
            raise ValueError("IMAP inbox could not be selected.")
        status, result = client.uid("search", None, "ALL")
        if status != "OK":
            raise ValueError("IMAP message search failed.")
        uids = result[0].split()[-limit:]
        for uid in uids:
            provider_id = f"imap:{connector.id}:{uid.decode(errors='replace')}"
            if InboundMessage.objects.filter(connector=messaging_connector, provider_message_id=provider_id).exists():
                continue
            status, fetched = client.uid("fetch", uid, "(BODY.PEEK[])")
            if status != "OK":
                continue
            raw = next((part[1] for part in fetched if isinstance(part, tuple)), None)
            if not raw:
                continue
            parsed = BytesParser(policy=policy.default).parsebytes(raw)
            body = ""
            has_attachments = False
            for part in parsed.walk():
                if part.get_filename():
                    has_attachments = True
                if not body and part.get_content_type() == "text/plain" and not part.get_filename():
                    body = part.get_content()
            subject = str(parsed.get("Subject", ""))
            decoded_subject = "".join(str(value) for value, _ in decode_header(subject))[:220]
            InboundMessage.objects.create(
                connector=messaging_connector,
                organization=organization,
                provider_message_id=provider_id,
                channel=InboundMessage.Channel.EMAIL,
                sender_address=str(parsed.get("From", ""))[:180],
                subject=decoded_subject,
                body_text=body[:10000],
                has_attachments=has_attachments,
                event_type="email.received",
            )
            created += 1
    finally:
        try:
            client.logout()
        except Exception:
            pass
    return {"created": created, "skipped": len(uids) - created, "message": "IMAP inbox synchronized."}

def register_gmail_watch(*, messaging_connector, email_connector, topic_name):
    """Register or renew a Gmail watch for one organization-owned mailbox."""
    if messaging_connector.organization_id is None or not messaging_connector.is_active:
        raise ValueError("The inbound email connector must be active and organization-owned.")
    if not isinstance(email_connector, EmailConnector) or email_connector.provider_type != "imap":
        raise ValueError("A receiving IMAP connector is required.")
    if not email_connector.is_active or not email_connector.oauth2_enabled:
        raise ValueError("The receiving connector must be active and use OAuth2.")
    assigned = email_connector.mailbox_access.filter(
        organization_id=messaging_connector.organization_id,
        connector=messaging_connector,
        is_active=True,
    ).exists()
    if not assigned:
        raise ValueError("The OAuth2 mailbox must be assigned to this inbound connector first.")
    if not topic_name.startswith("projects/") or "/topics/" not in topic_name:
        raise ValueError("Use a Google Pub/Sub topic name such as projects/PROJECT_ID/topics/TOPIC_ID.")
    access_token = _google_oauth_access_token_for_email(email_connector).get("access_token")
    payload = json.dumps({"topicName": topic_name, "labelIds": ["INBOX"]}).encode("utf-8")
    request = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/watch",
        data=payload,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise ValueError("Google rejected the Gmail watch request; check Gmail scope, topic access, and mailbox authorization.") from error
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise ValueError("Google Gmail watch registration could not be completed.") from error
    expiration = result.get("expiration")
    expiration_at = datetime.fromtimestamp(int(expiration) / 1000, tz=UTC) if expiration else None
    messaging_connector.gmail_topic_name = topic_name
    messaging_connector.gmail_history_id = str(result.get("historyId", ""))
    messaging_connector.gmail_watch_expiration = expiration_at
    messaging_connector.save(update_fields=("gmail_topic_name", "gmail_history_id", "gmail_watch_expiration", "updated_at"))
    return {
        "topic_name": topic_name,
        "history_id": messaging_connector.gmail_history_id,
        "expiration": expiration_at.isoformat() if expiration_at else None,
        "mailbox": email_connector.mailbox_address,
    }


def sync_gmail_pubsub_notification(*, messaging_connector, email_address):
    """Trigger the existing scoped IMAP sync from a Gmail push notification."""
    mailbox = (
        EmailConnector.objects.filter(
            provider_type="imap",
            is_active=True,
            oauth2_enabled=True,
            mailbox_address__iexact=email_address,
            mailbox_access__organization=messaging_connector.organization,
            mailbox_access__connector=messaging_connector,
            mailbox_access__is_active=True,
        )
        .order_by("-updated_at")
        .first()
    )
    if mailbox is None:
        return {"created": 0, "skipped": 0, "message": "No active assigned OAuth2 IMAP mailbox matches this Gmail account."}
    return sync_imap_mailbox(
        connector=mailbox,
        messaging_connector=messaging_connector,
        organization=messaging_connector.organization,
    )


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
