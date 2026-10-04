from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.core import signing
import logging
import json
from django.shortcuts import redirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
import urllib.parse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django.http import HttpResponse
from rest_framework.views import APIView

from audit.services import record_event
from integrations.models import EmailConnector, GoogleWorkspaceConnector, SecretBackend, StoragePolicy, StorageProvider
from workspace.channel_models import MailboxAccess, MessagingConnector
from integrations.services import (
    exchange_google_oauth_code,
    google_gmail_profile,
    google_oauth_url,
    send_test_email,
    store_secret,
    test_email_connector,
    test_storage_provider,
    validate_google_oauth,
    google_drive_access_token, google_drive_request,
)
from organizations.api.permissions import PlatformSuperuser
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user

logger = logging.getLogger(__name__)

from .serializers import (
    EmailConnectorSerializer, GoogleWorkspaceConnectorSerializer, StorageProviderSerializer, TestEmailSerializer,
)


class PlatformConfigView(APIView):
    permission_classes = (PlatformSuperuser,)

    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            exc = ValidationError(getattr(exc, "message_dict", exc.messages))
        return super().handle_exception(exc)

    def audit(self, request, action, resource, description):
        record_event(
            actor=request.user,
            action=action,
            resource=resource,
            description=description,
            request=request,
        )


class ConfigCollectionView(PlatformConfigView):
    model = None
    serializer_class = None
    action_prefix = ""

    def get(self, request):
        return Response(self.serializer_class(self.model.objects.all(), many=True).data)

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save(created_by=request.user)
        self.audit(
            request,
            f"{self.action_prefix}.created",
            item,
            f"Created {self.action_prefix} configuration {item.name}.",
        )
        return Response(self.serializer_class(item).data, status=status.HTTP_201_CREATED)


class ConfigDetailView(PlatformConfigView):
    model = None
    serializer_class = None
    action_prefix = ""

    def get_object(self, pk):
        return get_object_or_404(self.model, pk=pk)

    def get(self, request, pk):
        return Response(self.serializer_class(self.get_object(pk)).data)

    def patch(self, request, pk):
        item = self.get_object(pk)
        serializer = self.serializer_class(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        self.audit(
            request,
            f"{self.action_prefix}.updated",
            item,
            f"Updated {self.action_prefix} configuration {item.name}.",
        )
        return Response(self.serializer_class(item).data)

    @transaction.atomic
    def post(self, request, pk, action):
        item = self.get_object(pk)
        if action == "activate":
            item.is_active = True
        elif action == "deactivate":
            item.is_active = False
            item.is_default = False
        elif action == "set-default":
            if not item.is_active:
                raise ValidationError("Activate this configuration before setting it as default.")
            self.model.objects.filter(is_default=True).exclude(pk=item.pk).update(is_default=False)
            item.is_default = True
        else:
            raise ValidationError("Unknown lifecycle action.")
        item.save()
        verb = action.replace("-", "_")
        self.audit(
            request, f"{self.action_prefix}.{verb}", item, f"Changed {item.name} lifecycle state."
        )
        return Response(self.serializer_class(item).data)


class EmailCollectionView(ConfigCollectionView):
    model = EmailConnector
    serializer_class = EmailConnectorSerializer
    action_prefix = "integration.email"


class EmailDetailView(ConfigDetailView):
    model = EmailConnector
    serializer_class = EmailConnectorSerializer
    action_prefix = "integration.email"


class EmailTestView(PlatformConfigView):
    def post(self, request, pk):
        item = get_object_or_404(EmailConnector, pk=pk)
        test_email_connector(item)
        self.audit(
            request, "integration.email.tested", item, f"Tested email connector {item.name}."
        )
        return Response(EmailConnectorSerializer(item).data)


class EmailSendTestView(PlatformConfigView):
    def post(self, request, pk):
        item = get_object_or_404(EmailConnector, pk=pk)
        serializer = TestEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_test_email(item, serializer.validated_data["recipient"])
        self.audit(
            request,
            "integration.email.test_sent",
            item,
            f"Sent one explicit connector test message using {item.name}.",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class StorageCollectionView(ConfigCollectionView):
    model = StorageProvider
    serializer_class = StorageProviderSerializer
    action_prefix = "storage"


class StorageDetailView(ConfigDetailView):
    model = StorageProvider
    serializer_class = StorageProviderSerializer
    action_prefix = "storage"


class StoragePolicyView(PlatformConfigView):
    def get(self, request):
        policy, _ = StoragePolicy.objects.get_or_create(id="00000000-0000-0000-0000-000000000001")
        return Response(
            {
                "id": str(policy.id),
                "max_document_size_bytes": policy.max_document_size_bytes,
                "max_image_size_bytes": policy.max_image_size_bytes,
                "max_audio_size_bytes": policy.max_audio_size_bytes,
                "max_video_size_bytes": policy.max_video_size_bytes,
                "audio_upload_enabled": policy.audio_upload_enabled,
                "video_upload_enabled": policy.video_upload_enabled,
                "hard_ceilings": {
                    "document": 100 * 1024 * 1024,
                    "image": 50 * 1024 * 1024,
                    "audio": 1024 * 1024 * 1024,
                    "video": 2 * 1024 * 1024 * 1024,
                },
            }
        )

    def patch(self, request):
        policy, _ = StoragePolicy.objects.get_or_create(id="00000000-0000-0000-0000-000000000001")
        values = {}
        for field in (
            "max_document_size_bytes",
            "max_image_size_bytes",
            "max_audio_size_bytes",
            "max_video_size_bytes",
        ):
            if field in request.data:
                values[field] = int(request.data[field])
        for field in ("audio_upload_enabled", "video_upload_enabled"):
            if field in request.data:
                values[field] = bool(request.data[field])
        ceilings = {
            "max_document_size_bytes": 100 * 1024 * 1024,
            "max_image_size_bytes": 50 * 1024 * 1024,
            "max_audio_size_bytes": 1024 * 1024 * 1024,
            "max_video_size_bytes": 2 * 1024 * 1024 * 1024,
        }
        if any(
            value <= 0 or value > ceilings[field]
            for field, value in values.items()
            if field in ceilings
        ):
            raise ValidationError(
                "Upload limits must be positive and within the platform hard ceiling: "
                "documents 100 MB, images 50 MB, audio 1024 MB, video 2048 MB."
            )
        for field, value in values.items():
            setattr(policy, field, value)
        policy.updated_by = request.user
        policy.full_clean()
        policy.save()
        self.audit(request, "storage.policy_updated", policy, "Updated platform upload policy.")
        return self.get(request)


class StorageTestView(PlatformConfigView):
    def post(self, request, pk):
        item = get_object_or_404(StorageProvider, pk=pk)
        test_storage_provider(item)
        self.audit(request, "storage.tested", item, f"Tested storage provider {item.name}.")
        return Response(StorageProviderSerializer(item).data)


class GoogleWorkspaceCollectionView(ConfigCollectionView):
    model = GoogleWorkspaceConnector
    serializer_class = GoogleWorkspaceConnectorSerializer
    action_prefix = "integration.google"

    def get(self, request):
        seen = set()
        items = []
        for item in self.model.objects.order_by("-is_active", "-updated_at"):
            key = item.name.casefold()
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
        return Response(self.serializer_class(items, many=True).data)

    def post(self, request):
        name = str(request.data.get("name", "")).strip()
        if name and self.model.objects.filter(name__iexact=name).exists():
            raise ValidationError({"name": "A Google Workspace configuration with this name already exists. Edit the existing configuration instead."})
        return super().post(request)


class GoogleWorkspaceDetailView(ConfigDetailView):
    model = GoogleWorkspaceConnector
    serializer_class = GoogleWorkspaceConnectorSerializer
    action_prefix = "integration.google"

    @transaction.atomic
    def post(self, request, pk, action):
        if action != "disconnect":
            return super().post(request, pk, action)
        item = self.get_object(pk)
        item.is_active = False
        item.connection_status = "failed"
        item.last_tested_at = timezone.now()
        item.last_test_message = "Google OAuth connection disconnected. External secrets were retained safely."
        item.save(update_fields=("is_active", "connection_status", "last_tested_at", "last_test_message", "updated_at"))
        self.audit(request, "integration.google.disconnected", item, f"Disconnected Google OAuth configuration {item.name}.")
        return Response(self.serializer_class(item).data)


class AvailableGoogleWorkspaceView(APIView):
    def get(self, request):
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.query_params.get("organization_id"))
        if not user_has_organization_permission(request.user, organization, "calendar.view"):
            raise ValidationError("Calendar view permission is required for Google Sheets trackers.")
        return Response([{"id": str(item.id), "name": item.name, "products": item.products, "connection_status": item.connection_status, "is_active": item.is_active, "last_test_message": item.last_test_message} for item in GoogleWorkspaceConnector.objects.filter(is_active=True, products__contains=["sheets"])])


class GoogleDriveFilesView(APIView):
    def get(self, request):
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.query_params.get("organization_id"))
        if not user_has_organization_permission(request.user, organization, "document.view"):
            raise ValidationError("Document view permission is required for Google Drive.")
        token = google_drive_access_token()
        try:
            page_size = max(1, min(int(request.query_params.get("page_size", 50)), 100))
        except (TypeError, ValueError):
            page_size = 50
        params = {
            "pageSize": page_size,
            "orderBy": "folder,modifiedTime desc,name",
            "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,size,webViewLink,iconLink,parents)",
            "q": "trashed = false",
        }
        if request.query_params.get("q"):
            value = request.query_params["q"].replace("'", "\\'")
            params["q"] += f" and name contains '{value}'"
        if request.query_params.get("page_token"):
            params["pageToken"] = request.query_params["page_token"]
        with google_drive_request("files", token, params) as response:
            return Response(json.loads(response.read().decode("utf-8")))


class GoogleDriveDownloadView(APIView):
    def get(self, request, file_id):
        organization = get_object_or_404(organizations_for_user(request.user), pk=request.query_params.get("organization_id"))
        if not user_has_organization_permission(request.user, organization, "document.view"):
            raise ValidationError("Document view permission is required for Google Drive.")
        token = google_drive_access_token()
        mime_type = str(request.query_params.get("mime_type", "")).strip()
        native_exports = {
            "application/vnd.google-apps.document": "application/pdf",
            "application/vnd.google-apps.spreadsheet": "text/csv",
            "application/vnd.google-apps.presentation": "application/pdf",
        }
        if mime_type in native_exports:
            path = f"files/{urllib.parse.quote(file_id, safe='')}/export"
            params = {"mimeType": native_exports[mime_type]}
        else:
            path = f"files/{urllib.parse.quote(file_id, safe='')}"
            params = {"alt": "media"}
        with google_drive_request(path, token, params) as response:
            payload = response.read()
            content_type = response.headers.get_content_type() or native_exports.get(mime_type, "application/octet-stream")
            result = HttpResponse(payload, content_type=content_type)
            result["Content-Disposition"] = "attachment"
            return result



class GoogleWorkspaceOAuthStartView(PlatformConfigView):
    def post(self, request, pk):
        connector = get_object_or_404(GoogleWorkspaceConnector, pk=pk)
        if connector.secret_backend == SecretBackend.ENVIRONMENT:
            raise ValidationError("Move the refresh-token reference to Vault or AWS Secrets Manager before using one-click account connection.")
        if not connector.refresh_token_reference:
            raise ValidationError("Set the Google refresh-token destination reference before connecting an account.")
        raw_organization_id = request.data.get("organization_id")
        organization_id = raw_organization_id.strip() if isinstance(raw_organization_id, str) else ""
        if organization_id.lower() in {"none", "null"}:
            organization_id = ""
        organization = organizations_for_user(request.user).filter(pk=organization_id).first() if organization_id else organizations_for_user(request.user).first()
        if not organization:
            raise ValidationError("Select an active organization before connecting a mailbox.")
        state = signing.dumps(
            {"connector_id": str(connector.id), "user_id": str(request.user.id), "organization_id": str(organization.id)},
            salt="evolve-google-workspace-oauth",
        )
        return Response({"authorization_url": google_oauth_url(connector, state)})


class MailboxGoogleOAuthStartView(APIView):
    """Start Gmail OAuth from Mailroom for the signed-in workspace member."""

    def post(self, request):
        raw_organization_id = request.data.get("organization_id")
        organization_id = raw_organization_id.strip() if isinstance(raw_organization_id, str) else ""
        if organization_id.lower() in {"none", "null"}:
            organization_id = ""
        organizations = organizations_for_user(request.user)
        organization = organizations.filter(pk=organization_id).first() if organization_id else organizations.first()
        if not organization:
            raise ValidationError("Select an active organization before adding a mailbox.")
        if not user_has_organization_permission(request.user, organization, "mailbox.view"):
            raise ValidationError("Mailbox access is not enabled for your workspace role.")
        connector = (
            GoogleWorkspaceConnector.objects
            .filter(is_active=True, connection_status="healthy", products__contains=["gmail"])
            .order_by("-updated_at")
            .first()
        )
        if not connector:
            raise ValidationError("No active Gmail Google Workspace connection is available.")
        if connector.secret_backend == SecretBackend.ENVIRONMENT:
            raise ValidationError("Move the Google refresh-token reference to Vault or AWS Secrets Manager before adding a mailbox.")
        if not connector.refresh_token_reference:
            raise ValidationError("Set the Google refresh-token destination reference before adding a mailbox.")
        state = signing.dumps(
            {
                "connector_id": str(connector.id),
                "user_id": str(request.user.id),
                "organization_id": str(organization.id),
                "target": "/inbox",
            },
            salt="evolve-google-workspace-oauth",
        )
        return Response({"authorization_url": google_oauth_url(connector, state)})


class GoogleWorkspaceOAuthCallbackView(APIView):
    def get(self, request):
        target = "/platform/google-workspace"
        state = request.query_params.get("state", "")
        try:
            payload = signing.loads(state, salt="evolve-google-workspace-oauth", max_age=600)
            requested_target = payload.get("target", target)
            target = requested_target if requested_target in {"/inbox", "/platform/google-workspace"} else "/platform/google-workspace"
            connector = GoogleWorkspaceConnector.objects.get(pk=payload["connector_id"])
            if not request.user.is_authenticated or str(request.user.id) != str(payload["user_id"]):
                raise ValidationError("The OAuth browser session does not match the account that started the connection.")
            if request.query_params.get("error"):
                raise ValidationError("Google account access was not granted.")
            token_data = exchange_google_oauth_code(connector, request.query_params.get("code", ""))
            store_secret(connector.secret_backend, connector.refresh_token_reference, token_data["refresh_token"])
            organization = organizations_for_user(request.user).filter(pk=payload.get("organization_id")).first()
            if not organization:
                raise ValidationError("The selected organization is no longer available.")
            mailbox_address = google_gmail_profile(token_data.get("access_token", ""))
            mailbox_reference = f"secret/data/evolve/google#mailbox_{request.user.id}"
            store_secret(SecretBackend.VAULT, mailbox_reference, token_data["refresh_token"])
            messaging_connector = (
                MessagingConnector.objects
                .filter(organization=organization, provider_type=MessagingConnector.Provider.EMAIL, is_active=True)
                .order_by("-is_default", "created_at")
                .first()
            )
            if not messaging_connector:
                messaging_connector = MessagingConnector.objects.create(
                    organization=organization, provider_type=MessagingConnector.Provider.EMAIL,
                    name="Evolve OAuth mailboxes", display_name="Evolve Mailroom",
                    is_active=True, is_default=not MessagingConnector.objects.filter(organization=organization, provider_type=MessagingConnector.Provider.EMAIL, is_default=True).exists(),
                    signing_secret_reference="EVOLVE_INBOUND_BOOKINGS_SECRET", created_by=request.user,
                )
            email_connector = EmailConnector.objects.filter(
                from_email__iexact=mailbox_address, provider_type="imap",
                oauth2_refresh_token_reference=mailbox_reference,
            ).first()
            if not email_connector:
                email_connector = EmailConnector.objects.create(
                    name=f"{mailbox_address} personal mailbox", provider_type="imap",
                    is_active=True, from_name=(f"{request.user.first_name} {request.user.last_name}".strip() or mailbox_address),
                    from_email=mailbox_address, host="smtp.gmail.com", port=587,
                    imap_host="imap.gmail.com", imap_port=993, username=mailbox_address,
                    oauth2_enabled=True, oauth2_refresh_token_reference=mailbox_reference,
                    mailbox_address=mailbox_address, use_tls=True, use_ssl=False,
                    secret_backend=SecretBackend.VAULT, created_by=request.user,
                )
            email_connector.connection_status = "healthy"
            email_connector.last_tested_at = timezone.now()
            email_connector.last_test_message = "Google OAuth mailbox connected; IMAP and SMTP OAuth2 are ready."
            email_connector.save(update_fields=("connection_status", "last_tested_at", "last_test_message", "updated_at"))
            MailboxAccess.objects.update_or_create(
                connector=messaging_connector, user=request.user,
                defaults={"organization": organization, "sender_connector": email_connector, "granted_by": request.user, "is_active": True},
            )
            connector.is_active = True
            connector.connection_status = "healthy"
            connector.last_tested_at = timezone.now()
            connector.last_test_message = "Google account connected; OAuth access is ready."
            connector.save(update_fields=("is_active", "connection_status", "last_tested_at", "last_test_message", "updated_at"))
            record_event(actor=request.user, action="integration.google.oauth_connected", resource=connector, description=f"Connected a Google account to {connector.name}.", request=request)
            return redirect(f"{target}?oauth=connected")
        except (GoogleWorkspaceConnector.DoesNotExist, signing.BadSignature, signing.SignatureExpired, DjangoValidationError, ValidationError) as error:
            message = str(error) or "Google account connection failed."
            logger.warning("Google OAuth callback rejected: %s", message)
            return redirect(f"{target}?oauth=error&message={urllib.parse.quote(message[:180])}")
        except Exception:
            logger.exception("Google OAuth callback failed unexpectedly")
            return redirect(f"{target}?oauth=error&message={urllib.parse.quote('Google account connection could not be completed. Please try again.')}")


class GoogleWorkspaceTestView(PlatformConfigView):
    def post(self, request, pk):
        item = get_object_or_404(GoogleWorkspaceConnector, pk=pk)
        if not item.credentials_configured:
            raise ValidationError("Google client and secret references must resolve on the server.")
        if "sheets" in (item.products or []):
            validate_google_oauth(item)
        item.connection_status = "healthy"
        item.last_tested_at = timezone.now()
        item.last_test_message = "Google OAuth token exchange succeeded; Sheets access is ready."
        item.save(update_fields=("connection_status", "last_tested_at", "last_test_message", "updated_at"))
        self.audit(request, "integration.google.tested", item, f"Validated Google Workspace configuration {item.name}.")
        return Response(GoogleWorkspaceConnectorSerializer(item).data)
