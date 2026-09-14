from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils.http import content_disposition_header
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from artists.models import Artist
from audit.services import record_event
from bookings.models import Booking
from callsheets.models import CallSheet
from campaigns.models import Campaign
from documents.file_validation import INLINE_TYPES
from documents.models import Document, DocumentLink
from documents.selectors import developer_documents, documents_for_user, portal_documents
from documents.services import (
    archive_document,
    create_document,
    create_version,
    duplicate_office_document,
    link_document,
    move_document_to_workspace,
    restore_document,
    unlink_document,
    update_document,
    upload_document,
    upload_new_version,
)
from documents.storage import DocumentStorageUnavailable, get_storage_backend, storage_status
from music.models import Release
from organizations.api.permissions import PlatformSuperuser
from organizations.selectors import organizations_for_user
from production.models import ProductionAdvance
from travel.models import AccommodationStay, TravelItinerary, TravelSegment
from white_label.services import authenticate_api_key
from workspace.models import Workspace

from .serializers import (
    DeveloperDocumentSerializer,
    DocumentSerializer,
    DocumentUploadSerializer,
    DocumentVersionUploadSerializer,
    PlatformDocumentSummarySerializer,
    PortalDocumentSerializer,
)


class StorageUnavailable(APIException):
    status_code = 503
    default_detail = "Private file storage is unavailable."


def org_for(user, request):
    pk = request.query_params.get("organization") or request.data.get("organization")
    if not pk:
        raise ValidationError({"organization": "Organization is required."})
    return get_object_or_404(organizations_for_user(user), pk=pk)


def scoped(user, org, pk):
    document = documents_for_user(user, org).filter(pk=pk).first()
    if document:
        return document
    return get_object_or_404(portal_documents(user, org), pk=pk)


def filter_documents(qs, request):
    search = request.query_params.get("search")
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(original_filename__icontains=search))
    for parameter, field in (
        ("type", "document_type"),
        ("source", "source_type"),
        ("status", "status"),
        ("visibility", "visibility"),
        ("uploader", "uploaded_by_id"),
        ("artist", "links__artist_id"),
        ("booking", "links__booking_id"),
        ("release", "links__release_id"),
        ("campaign", "links__campaign_id"),
    ):
        if request.query_params.get(parameter):
            qs = qs.filter(**{field: request.query_params[parameter]})
    if request.query_params.get("date_from"):
        qs = qs.filter(created_at__date__gte=request.query_params["date_from"])
    if request.query_params.get("date_to"):
        qs = qs.filter(created_at__date__lte=request.query_params["date_to"])
    return qs.distinct()


class DocumentListView(APIView):
    def get(self, request):
        org = org_for(request.user, request)
        documents = filter_documents(documents_for_user(request.user, org), request)
        return Response(DocumentSerializer(documents, many=True, context={"request": request}).data)

    def post(self, request):
        org = org_for(request.user, request)
        serializer = DocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            document = create_document(
                actor=request.user, organization=org, request=request, **serializer.validated_data
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(DocumentSerializer(document, context={"request": request}).data, status=201)


class DocumentUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        org = org_for(request.user, request)
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        file = data.pop("file")
        try:
            document = upload_document(
                actor=request.user, organization=org, file=file, request=request, **data
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except DjangoValidationError as exc:
            raise ValidationError(getattr(exc, "message_dict", exc.messages)) from exc
        except DocumentStorageUnavailable as exc:
            raise StorageUnavailable() from exc
        return Response(DocumentSerializer(document, context={"request": request}).data, status=201)


class StorageStatusView(APIView):
    def get(self, request):
        org_for(request.user, request)
        return Response(
            {**storage_status(), "maximum_upload_bytes": settings.EVOLVE_MAX_UPLOAD_BYTES}
        )


class DocumentDetailView(APIView):
    def get(self, request, document_id):
        org = org_for(request.user, request)
        document = scoped(request.user, org, document_id)
        return Response(DocumentSerializer(document, context={"request": request}).data)

    def patch(self, request, document_id):
        org = org_for(request.user, request)
        document = scoped(request.user, org, document_id)
        serializer = DocumentSerializer(document, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            document = update_document(
                document, actor=request.user, request=request, **serializer.validated_data
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(DocumentSerializer(document, context={"request": request}).data)


class ArchiveView(APIView):
    def post(self, request, document_id):
        org = org_for(request.user, request)
        try:
            document = archive_document(
                scoped(request.user, org, document_id), actor=request.user, request=request
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(DocumentSerializer(document, context={"request": request}).data)


class RestoreView(APIView):
    def post(self, request, document_id):
        org = org_for(request.user, request)
        try:
            document = restore_document(
                scoped(request.user, org, document_id), actor=request.user, request=request
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(DocumentSerializer(document, context={"request": request}).data)


class OfficeDuplicateView(APIView):
    def post(self, request, document_id):
        org = org_for(request.user, request)
        document = scoped(request.user, org, document_id)
        try:
            copy = duplicate_office_document(
                document, actor=request.user, title=request.data.get("title"), request=request
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(DocumentSerializer(copy, context={"request": request}).data, status=201)


class OfficeMoveView(APIView):
    def post(self, request, document_id):
        org = org_for(request.user, request)
        document = scoped(request.user, org, document_id)
        workspace_id = request.data.get("workspace_id")
        workspace = None
        if workspace_id:
            workspace = get_object_or_404(
                Workspace, pk=workspace_id, organization=org, archived=False
            )
        try:
            moved = move_document_to_workspace(
                document, actor=request.user, workspace=workspace, request=request
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(DocumentSerializer(moved, context={"request": request}).data)


class VersionView(APIView):
    def get(self, request, document_id):
        org = org_for(request.user, request)
        document = scoped(request.user, org, document_id)
        root_id = document.parent_document_id or document.pk
        lineage = (
            documents_for_user(request.user, org)
            .filter(Q(pk=root_id) | Q(parent_document_id=root_id))
            .order_by("version_number")
        )
        return Response(DocumentSerializer(lineage, many=True, context={"request": request}).data)

    def post(self, request, document_id):
        org = org_for(request.user, request)
        document = scoped(request.user, org, document_id)
        serializer = DocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            version = create_version(
                document, actor=request.user, request=request, **serializer.validated_data
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(DocumentSerializer(version, context={"request": request}).data, status=201)


class VersionUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, document_id):
        org = org_for(request.user, request)
        document = scoped(request.user, org, document_id)
        serializer = DocumentVersionUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            version = upload_new_version(
                document=document,
                actor=request.user,
                request=request,
                **serializer.validated_data,
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except DjangoValidationError as exc:
            raise ValidationError(getattr(exc, "message_dict", exc.messages)) from exc
        except DocumentStorageUnavailable as exc:
            raise StorageUnavailable() from exc
        return Response(DocumentSerializer(version, context={"request": request}).data, status=201)


def _stream_body(body, chunk_size=64 * 1024):
    try:
        while chunk := body.read(chunk_size):
            yield chunk
    finally:
        close = getattr(body, "close", None)
        if close:
            close()


class DocumentContentView(APIView):
    preview = False

    def get(self, request, document_id):
        org = org_for(request.user, request)
        document = scoped(request.user, org, document_id)
        if document.source_type != Document.SourceType.STORED:
            raise ValidationError("This Document does not contain a stored file.")
        if document.storage_status != Document.StorageStatus.AVAILABLE:
            raise ValidationError("This stored file is not available.")
        if self.preview and document.detected_content_type not in INLINE_TYPES:
            raise ValidationError("This file type cannot be previewed safely.")
        try:
            stored = get_storage_backend(document.storage_provider).open_stream(
                document.storage_key
            )
        except DocumentStorageUnavailable as exc:
            raise StorageUnavailable("The stored file is temporarily unavailable.") from exc
        response = StreamingHttpResponse(
            _stream_body(stored.body), content_type=document.detected_content_type
        )
        response["Content-Disposition"] = content_disposition_header(
            not self.preview, document.original_filename
        )
        response["Cache-Control"] = "private, no-store, max-age=0"
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        if stored.content_length:
            response["Content-Length"] = stored.content_length
        record_event(
            actor=request.user,
            organization=document.organization,
            action="document.previewed" if self.preview else "document.downloaded",
            resource=document,
            description=f"Document version {document.version_number} accessed.",
            request=request,
        )
        return response


class DocumentDownloadView(DocumentContentView):
    preview = False


class DocumentPreviewView(DocumentContentView):
    preview = True


ENTITY_MODELS = {
    "artist": Artist,
    "booking": Booking,
    "call_sheet": CallSheet,
    "release": Release,
    "campaign": Campaign,
    "travel_itinerary": TravelItinerary,
    "travel_segment": TravelSegment,
    "accommodation_stay": AccommodationStay,
    "production_advance": ProductionAdvance,
}


class LinkView(APIView):
    def post(self, request, document_id):
        org = org_for(request.user, request)
        document = scoped(request.user, org, document_id)
        entity_type = request.data.get("entity_type")
        if entity_type not in ENTITY_MODELS:
            raise ValidationError({"entity_type": "Unsupported entity type."})
        organization_field = (
            "itinerary__organization"
            if entity_type in {"travel_segment", "accommodation_stay"}
            else "organization"
        )
        entity = get_object_or_404(
            ENTITY_MODELS[entity_type],
            pk=request.data.get("entity_id"),
            **{organization_field: org},
        )
        try:
            link = link_document(
                document, actor=request.user, request=request, **{entity_type: entity}
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response({"id": link.pk}, status=201)


class LinkDetailView(APIView):
    def delete(self, request, document_id, link_id):
        org = org_for(request.user, request)
        document = scoped(request.user, org, document_id)
        link = get_object_or_404(DocumentLink, document=document, pk=link_id)
        try:
            unlink_document(link, actor=request.user, request=request)
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(status=204)


class PortalDocumentsView(APIView):
    def get(self, request):
        org = org_for(request.user, request)
        return Response(
            PortalDocumentSerializer(
                portal_documents(request.user, org), many=True, context={"request": request}
            ).data
        )


class PlatformDocumentListView(APIView):
    permission_classes = [PlatformSuperuser]

    def get(self, request):
        documents = (
            Document.objects.all()
            .select_related("organization")
            .prefetch_related(
                "links__artist",
                "links__booking",
                "links__call_sheet",
                "links__release",
                "links__campaign",
            )
        )
        return Response(
            PlatformDocumentSummarySerializer(
                filter_documents(documents, request), many=True, context={"request": request}
            ).data
        )


class PlatformDocumentDetailView(APIView):
    permission_classes = [PlatformSuperuser]

    def get(self, request, document_id):
        document = get_object_or_404(Document.objects.prefetch_related("links"), pk=document_id)
        return Response(DocumentSerializer(document, context={"request": request}).data)


class DeveloperDocumentsView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise PermissionDenied()
        key = authenticate_api_key(header[7:], required_scope="document.read")
        return Response(
            DeveloperDocumentSerializer(
                developer_documents(key.client.organization), many=True
            ).data
        )
