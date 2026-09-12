from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import record_event
from integrations.models import EmailConnector, StoragePolicy, StorageProvider
from integrations.services import send_test_email, test_email_connector, test_storage_provider
from organizations.api.permissions import PlatformSuperuser

from .serializers import EmailConnectorSerializer, StorageProviderSerializer, TestEmailSerializer


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
                "Upload limits must be positive and within the platform hard ceiling."
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
