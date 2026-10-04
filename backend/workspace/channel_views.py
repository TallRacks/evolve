import base64
import json

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from django.core.validators import validate_email
import os
from audit.services import record_event
from integrations.models import EmailConnector
from integrations.services import send_application_email
from documents.models import Document
from documents.selectors import documents_for_user
from documents.storage import DocumentStorageUnavailable, get_storage_backend

from .channel_models import ChannelVerification, InboundMessage, MailboxAccess, MailboxReply, MailboxSentMessage, MessagingConnector, MessagingIdentity
from .channel_services import accept_inbound, command_result, register_gmail_watch, resolve_identity, sync_gmail_pubsub_notification, sync_imap_mailbox, verification_code, verify_signature
from organizations.selectors import organizations_for_user
from organizations.permissions import user_has_organization_permission


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


class GmailPubSubWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, connector_id):
        connector = get_object_or_404(
            MessagingConnector,
            pk=connector_id,
            provider_type=MessagingConnector.Provider.EMAIL,
            is_active=True,
        )
        if connector.organization_id is None:
            return Response({"detail": "Gmail push connectors must belong to an organization."}, status=status.HTTP_400_BAD_REQUEST)
        expected_token = os.environ.get("EVOLVE_GMAIL_PUBSUB_TOKEN", "")
        supplied_token = request.query_params.get("token", "")
        if not expected_token or not supplied_token or not hmac_compare(supplied_token, expected_token):
            return Response({"detail": "Invalid Gmail push authorization."}, status=status.HTTP_403_FORBIDDEN)
        envelope = request.data if isinstance(request.data, dict) else {}
        message = envelope.get("message")
        if not isinstance(message, dict):
            return Response({"detail": "Invalid Pub/Sub envelope."}, status=status.HTTP_400_BAD_REQUEST)
        encoded = message.get("data")
        if not encoded:
            return Response({"status": "acknowledged", "created": 0})
        try:
            notification = json.loads(base64.b64decode(encoded).decode("utf-8"))
            email_address = str(notification.get("emailAddress", "")).strip().lower()
            if "@" not in email_address:
                raise ValueError("Gmail notification did not contain a mailbox address.")
            result = sync_gmail_pubsub_notification(messaging_connector=connector, email_address=email_address)
        except (ValueError, TypeError, json.JSONDecodeError):
            return Response({"detail": "Invalid Gmail notification payload."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"detail": "Gmail notification processing failed."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"status": "acknowledged", "email_address": email_address, **result})


class GmailWatchView(APIView):
    def post(self, request):
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.data.get("organization_id"))
        if not user_has_organization_permission(request.user, organization, "mailbox.manage"):
            return Response({"detail": "Mailbox management permission required."}, status=status.HTTP_403_FORBIDDEN)
        connector = get_object_or_404(
            MessagingConnector,
            pk=request.data.get("connector_id"),
            organization=organization,
            provider_type=MessagingConnector.Provider.EMAIL,
            is_active=True,
        )
        topic_name = str(request.data.get("topic_name", "")).strip()
        access_qs = MailboxAccess.objects.filter(
            organization=organization,
            connector=connector,
            is_active=True,
        ).select_related("sender_connector")
        if request.data.get("sender_connector_id"):
            access_qs = access_qs.filter(sender_connector_id=request.data.get("sender_connector_id"))
        if request.data.get("mailbox_address"):
            access_qs = access_qs.filter(sender_connector__mailbox_address__iexact=str(request.data.get("mailbox_address")).strip())
        access = access_qs.filter(
            sender_connector__provider_type="imap",
            sender_connector__is_active=True,
            sender_connector__oauth2_enabled=True,
        ).first()
        if access is None or access.sender_connector is None:
            return Response({"detail": "Assign an active OAuth2 IMAP mailbox to this connector first."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = register_gmail_watch(
                messaging_connector=connector,
                email_connector=access.sender_connector,
                topic_name=topic_name,
            )
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        record_event(
            actor=request.user,
            organization=organization,
            action="mailbox.gmail_watch_registered",
            resource=connector,
            description="Registered Gmail push notifications for an assigned mailbox.",
            request=request,
        )
        return Response({"status": "watching", "connector_id": str(connector.id), **result})


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


class MailboxView(APIView):
    def get(self, request):
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.query_params.get("organization_id"))
        grants = MailboxAccess.objects.filter(organization=organization, user=request.user, is_active=True).select_related("connector", "sender_connector")
        connector_ids = list(grants.values_list("connector_id", flat=True))
        selected_connector = str(request.query_params.get("connector_id", "")).strip()
        if selected_connector:
            connector_ids = [connector_id for connector_id in connector_ids if str(connector_id) == selected_connector]
        query = str(request.query_params.get("q", "")).strip()
        folder = request.query_params.get("folder", "all")
        messages_qs = InboundMessage.objects.filter(connector_id__in=connector_ids, organization=organization, channel=InboundMessage.Channel.EMAIL)
        if query:
            from django.db.models import Q
            messages_qs = messages_qs.filter(Q(sender_address__icontains=query) | Q(subject__icontains=query) | Q(body_text__icontains=query))
        if folder in {"inbox", "unread"}:
            messages_qs = messages_qs.filter(folder=InboundMessage.Folder.INBOX)
        elif folder == "archived":
            messages_qs = messages_qs.filter(folder=InboundMessage.Folder.ARCHIVED)
        elif folder == "deleted":
            messages_qs = messages_qs.filter(folder=InboundMessage.Folder.DELETED)
        else:
            # “All mail” includes retained messages; deleted mail remains in Deleted.
            messages_qs = messages_qs.exclude(folder=InboundMessage.Folder.DELETED)
        if folder == "unread":
            messages_qs = messages_qs.filter(is_read=False)
        try:
            page = max(int(request.query_params.get("page", 1)), 1)
            page_size = min(max(int(request.query_params.get("page_size", 20)), 10), 50)
        except ValueError as error:
            raise ValidationError("Mailbox page and page_size must be integers.") from error
        message_total = messages_qs.count()
        messages = messages_qs.order_by("-created_at")[(page - 1) * page_size : page * page_size]
        sent_qs = MailboxSentMessage.objects.filter(connector_id__in=connector_ids, organization=organization)
        if query:
            from django.db.models import Q
            sent_qs = sent_qs.filter(Q(recipient_address__icontains=query) | Q(subject__icontains=query) | Q(body_text__icontains=query))
        sent_folder = {"sent": MailboxSentMessage.Folder.SENT, "drafts": MailboxSentMessage.Folder.DRAFTS, "outbox": MailboxSentMessage.Folder.OUTBOX, "deleted": MailboxSentMessage.Folder.DELETED}.get(folder)
        sent_total = sent_qs.filter(folder=sent_folder).count() if sent_folder else 0
        sent = list(sent_qs.filter(folder=sent_folder).order_by("-created_at")[(page - 1) * page_size : page * page_size]) if sent_folder else []
        people = [{"id": str(item.user_id), "name": f"{item.user.first_name} {item.user.last_name}".strip() or item.user.email, "email": item.user.email} for item in organization.memberships.active().select_related("user")]
        return Response({"people": people, "mailboxes": [{"id": grant.id, "connector": grant.connector.name, "connector_id": grant.connector_id, "sender_connector_id": grant.sender_connector_id, "sender": grant.sender_connector.from_email if grant.sender_connector else "Default sender", "is_active": grant.is_active} for grant in grants], "messages": [{"id": item.id, "sender": item.sender_address, "subject": item.subject, "body": item.body_text, "has_attachments": item.has_attachments, "is_read": item.is_read, "folder": item.folder, "received_at": item.created_at, "replies": [{"id": reply.id, "sender": reply.sender_address, "body": reply.body_text, "status": reply.status, "sent_at": reply.created_at} for reply in item.replies.order_by("created_at")]} for item in messages], "sent": [{"id": item.id, "sender": item.sender_address, "recipient": item.recipient_address, "folder": item.folder, "subject": item.subject, "body": item.body_text, "status": item.status, "sent_at": item.created_at} for item in sent], "pagination": {"page": page, "page_size": page_size, "message_total": message_total, "sent_total": sent_total, "message_pages": (message_total + page_size - 1) // page_size, "sent_pages": (sent_total + page_size - 1) // page_size}})


class MailboxSyncView(APIView):
    def post(self, request):
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.data.get("organization_id"))
        grants = MailboxAccess.objects.filter(organization=organization, user=request.user, is_active=True).select_related("connector", "sender_connector")
        connector_id = request.data.get("connector_id")
        if connector_id:
            grants = grants.filter(connector_id=connector_id)
        results = []
        for grant in grants:
            if not grant.sender_connector or grant.sender_connector.provider_type != "imap":
                continue
            try:
                result = sync_imap_mailbox(connector=grant.sender_connector, messaging_connector=grant.connector, organization=organization)
            except Exception as error:
                result = {"created": 0, "skipped": 0, "message": f"Mailbox sync failed ({error.__class__.__name__})."}
            results.append({"connector_id": str(grant.connector_id), "connector": grant.connector.name, **result})
        if not results:
            return Response({"detail": "No assigned IMAP mailbox connector is available for synchronization."}, status=400)
        return Response({"results": results, "created": sum(item["created"] for item in results)})


class MailboxMessageReadView(APIView):
    def post(self, request, message_id):
        message = get_object_or_404(InboundMessage, pk=message_id, channel=InboundMessage.Channel.EMAIL)
        organization = message.organization or get_object_or_404(organizations_for_user(request.user), pk=request.data.get("organization_id"))
        if not MailboxAccess.objects.filter(organization=organization, connector=message.connector, user=request.user, is_active=True).exists():
            return Response({"detail": "You do not have access to this mailbox."}, status=403)
        if not message.is_read:
            message.is_read = True
            message.save(update_fields=("is_read", "updated_at"))
        return Response({"status": "read"})


class MailboxComposeView(APIView):
    def post(self, request):
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.data.get("organization_id"))
        connector_id = request.data.get("connector_id")
        grant_qs = MailboxAccess.objects.filter(organization=organization, user=request.user, is_active=True).select_related("connector", "sender_connector")
        grant = get_object_or_404(grant_qs, connector_id=connector_id) if connector_id else grant_qs.first()
        if not grant:
            return Response({"detail": "You do not have an active mailbox assignment."}, status=403)
        recipients = request.data.get("recipients", []) or []
        if isinstance(recipients, str):
            recipients = [item.strip() for item in recipients.split(",") if item.strip()]
        if not isinstance(recipients, list):
            raise ValidationError("Recipients must be an array or comma-separated addresses.")
        recipients = [str(item).strip() for item in recipients if str(item).strip()]
        if not recipients and request.data.get("recipient"):
            recipients = [str(request.data.get("recipient")).strip()]
        recipient = ", ".join(recipients)
        subject = str(request.data.get("subject", "")).strip()[:220]
        body = str(request.data.get("body", "")).strip()
        save_draft = bool(request.data.get("save_draft"))
        cc = request.data.get("cc", []) or []
        bcc = request.data.get("bcc", []) or []
        attachment_document_ids = request.data.get("attachment_document_ids", []) or []
        tagged_user_ids = request.data.get("tagged_user_ids", []) or []
        if isinstance(cc, str):
            cc = [item.strip() for item in cc.split(",") if item.strip()]
        if isinstance(bcc, str):
            bcc = [item.strip() for item in bcc.split(",") if item.strip()]
        if not isinstance(cc, list) or not isinstance(bcc, list) or not isinstance(attachment_document_ids, list) or not isinstance(tagged_user_ids, list):
            raise ValidationError("CC, BCC, attachment references, and tagged people must be arrays or comma-separated addresses.")
        documents = list(documents_for_user(request.user, organization).filter(pk__in=attachment_document_ids, source_type=Document.SourceType.STORED, status=Document.Status.ACTIVE))
        if len(documents) != len(set(str(item) for item in attachment_document_ids)):
            raise ValidationError("One or more attachments are unavailable in your workspace.")
        people = list(organization.memberships.active().filter(user_id__in=tagged_user_ids).values_list("user_id", flat=True))
        if len(people) != len(set(str(item) for item in tagged_user_ids)):
            raise ValidationError("One or more tagged people are not active workspace members.")
        for address in [*recipients, *cc, *bcc]:
            try:
                validate_email(address)
            except Exception as exc:
                raise ValidationError(f"Invalid email address: {address}.") from exc
        if not recipients and not save_draft:
            raise ValidationError("Add at least one recipient.")
        if len(body) > 10000:
            raise ValidationError("Message body is required and must be under 10,000 characters.")
        sender = grant.sender_connector or EmailConnector.objects.filter(is_active=True, is_default=True).first()
        if sender is None:
            raise ValidationError("No active default email sender is configured.")
        attachments = []
        try:
            for document in documents:
                stored = get_storage_backend(document.storage_provider).open_stream(document.storage_key)
                attachments.append({"filename": document.original_filename or document.title, "content_type": document.detected_content_type or document.content_type or "application/octet-stream", "content": stored.body.read()})
        except DocumentStorageUnavailable as error:
            raise ValidationError("An attachment could not be read from private storage.") from error
        if not save_draft:
            send_application_email(sender, recipient, subject, body, f"<p>{body.replace(chr(10), '<br>')}</p>", cc=cc, bcc=bcc, attachments=attachments)
        sent = MailboxSentMessage.objects.create(connector=grant.connector, organization=organization, sender_address=sender.from_email, recipient_address=recipient, folder=MailboxSentMessage.Folder.DRAFTS if save_draft else MailboxSentMessage.Folder.SENT, status=MailboxSentMessage.Status.DRAFT if save_draft else MailboxSentMessage.Status.SENT, cc_addresses=cc, bcc_addresses=bcc, attachment_document_ids=[str(item) for item in attachment_document_ids], tagged_user_ids=[str(item) for item in tagged_user_ids], subject=subject, body_text=body, sent_by=request.user)
        record_event(actor=request.user, organization=organization, action="mailbox.message_sent", resource=sent, description="Sent a mailbox message.", request=request)
        return Response({"id": sent.id, "status": sent.status, "sent_at": sent.created_at}, status=201)


class MailboxMessageFolderView(APIView):
    def post(self, request, message_id, action):
        message = get_object_or_404(InboundMessage, pk=message_id, channel=InboundMessage.Channel.EMAIL)
        organization = message.organization or get_object_or_404(organizations_for_user(request.user), pk=request.data.get("organization_id"))
        if not MailboxAccess.objects.filter(organization=organization, connector=message.connector, user=request.user, is_active=True).exists():
            return Response({"detail": "You do not have access to this mailbox."}, status=403)
        folders = {"archive": InboundMessage.Folder.ARCHIVED, "delete": InboundMessage.Folder.DELETED, "restore": InboundMessage.Folder.INBOX}
        if action not in folders:
            raise ValidationError("Unsupported mailbox folder action.")
        message.folder = folders[action]
        message.save(update_fields=("folder", "updated_at"))
        record_event(actor=request.user, organization=organization, action=f"mailbox.message_{action}d", resource=message, description=f"Moved a message to {message.folder}.", request=request)
        return Response({"id": message.id, "folder": message.folder})


class MailboxAccessView(APIView):
    def get(self, request):
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.query_params.get("organization_id"))
        if not user_has_organization_permission(request.user, organization, "mailbox.manage"):
            return Response({"access": []})
        accesses = MailboxAccess.objects.filter(organization=organization).select_related("user", "connector")
        connectors = MessagingConnector.objects.filter(provider_type=MessagingConnector.Provider.EMAIL).filter(organization__isnull=True) | MessagingConnector.objects.filter(provider_type=MessagingConnector.Provider.EMAIL, organization=organization)
        members = organization.memberships.active().select_related("user")
        mailbox_sender_ids = set(MailboxAccess.objects.filter(organization=organization, is_active=True).values_list("sender_connector_id", flat=True))
        sender_statuses = dict(EmailConnector.objects.filter(id__in=mailbox_sender_ids).values_list("id", "connection_status"))
        connector_data = []
        for item in connectors:
            sender_status = next((sender_statuses.get(access.sender_connector_id) for access in accesses if access.connector_id == item.id and access.sender_connector_id), None)
            status = sender_status or item.webhook_status
            connector_data.append({"id": item.id, "name": item.name, "active": item.is_active, "status": status})
        return Response({"access": [{"id": item.id, "user_id": item.user_id, "user": f"{item.user.first_name} {item.user.last_name}".strip() or item.user.email, "connector_id": item.connector_id, "connector": item.connector.name, "sender": item.sender_connector.from_email if item.sender_connector else "Default sender", "is_active": item.is_active} for item in accesses], "connectors": connector_data, "senders": [{"id": item.id, "name": item.name, "from_name": item.from_name, "from_email": item.from_email, "provider_type": item.provider_type, "oauth2_enabled": item.oauth2_enabled, "mailbox_address": item.mailbox_address} for item in EmailConnector.objects.filter(is_active=True)], "members": [{"id": item.id, "user_id": item.user_id, "name": f"{item.user.first_name} {item.user.last_name}".strip() or item.user.email} for item in members]})

    def post(self, request):
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.data.get("organization_id"))
        if not user_has_organization_permission(request.user, organization, "mailbox.manage"):
            return Response({"detail": "Mailbox management permission required."}, status=403)
        connector = get_object_or_404(MessagingConnector, pk=request.data.get("connector_id"), provider_type=MessagingConnector.Provider.EMAIL, is_active=True)
        sender_connector = None
        if request.data.get("sender_connector_id"):
            sender_connector = get_object_or_404(EmailConnector, pk=request.data.get("sender_connector_id"), is_active=True)
        membership = get_object_or_404(organization.memberships.active(), pk=request.data.get("membership_id"))
        if connector.organization_id not in (None, organization.id):
            return Response({"detail": "Connector is not available to this organization."}, status=400)
        access, _ = MailboxAccess.objects.update_or_create(connector=connector, user=membership.user, defaults={"organization": organization, "sender_connector": sender_connector, "granted_by": request.user, "is_active": True})
        record_event(actor=request.user, organization=organization, action="mailbox.access_granted", resource=access, description=f"Granted mailbox access to {membership.user.email}.", request=request)
        return Response({"id": access.id, "status": "active"}, status=201)


class MailboxAccessDetailView(APIView):
    def delete(self, request, access_id):
        access = get_object_or_404(MailboxAccess.objects.select_related("organization", "user"), pk=access_id)
        if access.user_id != request.user.id and not user_has_organization_permission(request.user, access.organization, "mailbox.manage"):
            return Response({"detail": "Mailbox management permission required."}, status=403)
        access.is_active = False
        access.save(update_fields=("is_active", "updated_at"))
        record_event(actor=request.user, organization=access.organization, action="mailbox.access_revoked", resource=access, description=f"Revoked mailbox access for {access.user.email}.", request=request)
        return Response({"status": "revoked"})


class MailboxReplyView(APIView):
    def post(self, request, message_id):
        message = get_object_or_404(InboundMessage.objects.select_related("organization", "connector"), pk=message_id, channel=InboundMessage.Channel.EMAIL)
        organization = message.organization or get_object_or_404(organizations_for_user(request.user), pk=request.data.get("organization_id"))
        if not MailboxAccess.objects.filter(organization=organization, connector=message.connector, user=request.user, is_active=True).exists():
            return Response({"detail": "You do not have access to this mailbox."}, status=403)
        reply_all = bool(request.data.get("reply_all"))
        body = str(request.data.get("body", "")).strip()
        if not body or len(body) > 10000:
            raise ValidationError("Reply body is required and must be under 10,000 characters.")
        try:
            validate_email(message.sender_address)
        except Exception as exc:
            raise ValidationError("This message sender cannot receive replies.") from exc
        connector = message.connector.mailbox_access.filter(organization=organization, user=request.user, is_active=True).select_related("sender_connector").first().sender_connector or EmailConnector.objects.filter(is_active=True, is_default=True).first()
        if connector is None:
            raise ValidationError("No active default email sender is configured.")
        subject = message.subject if message.subject.lower().startswith("re:") else f"Re: {message.subject}"
        send_application_email(connector, message.sender_address, subject[:220], body, f"<p>{body.replace(chr(10), '<br>')}</p>")
        reply = MailboxReply.objects.create(message=message, organization=organization, sender_address=connector.from_email, recipient_address=message.sender_address, subject=subject[:220], body_text=body, status=MailboxReply.Status.SENT, sent_by=request.user)
        record_event(actor=request.user, organization=organization, action="mailbox.reply_sent", resource=reply, description=("Sent a mailbox reply-all." if reply_all else "Sent a mailbox reply."), request=request)
        return Response({"id": reply.id, "status": reply.status, "sent_at": reply.created_at}, status=201)
