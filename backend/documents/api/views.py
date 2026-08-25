from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from artists.models import Artist
from bookings.models import Booking
from callsheets.models import CallSheet
from campaigns.models import Campaign
from documents.models import Document, DocumentLink
from documents.selectors import developer_documents, documents_for_user, portal_documents
from documents.services import (
    archive_document,
    create_document,
    create_version,
    link_document,
    unlink_document,
    update_document,
)
from music.models import Release
from organizations.api.permissions import PlatformSuperuser
from organizations.selectors import organizations_for_user
from travel.models import AccommodationStay, TravelItinerary, TravelSegment
from white_label.services import authenticate_api_key

from .serializers import (
    DeveloperDocumentSerializer,
    DocumentSerializer,
    PlatformDocumentSummarySerializer,
    PortalDocumentSerializer,
)


def org_for(user, request):
    pk = request.query_params.get("organization") or request.data.get("organization")
    if not pk:
        raise ValidationError({"organization": "Organization is required."})
    return get_object_or_404(organizations_for_user(user), pk=pk)


def scoped(user, org, pk):
    return get_object_or_404(documents_for_user(user, org), pk=pk)


def filter_documents(qs, request):
    search = request.query_params.get("search")
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(original_filename__icontains=search))
    for parameter, field in (
        ("type", "document_type"),
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
        return Response(
            DocumentSerializer(
                filter_documents(documents_for_user(request.user, org), request), many=True
            ).data
        )

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
        return Response(DocumentSerializer(document).data, status=201)


class DocumentDetailView(APIView):
    def get(self, request, document_id):
        org = org_for(request.user, request)
        return Response(DocumentSerializer(scoped(request.user, org, document_id)).data)

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
        return Response(DocumentSerializer(document).data)


class ArchiveView(APIView):
    def post(self, request, document_id):
        org = org_for(request.user, request)
        try:
            document = archive_document(
                scoped(request.user, org, document_id), actor=request.user, request=request
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(DocumentSerializer(document).data)


class VersionView(APIView):
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
        return Response(DocumentSerializer(version).data, status=201)


ENTITY_MODELS = {
    "artist": Artist,
    "booking": Booking,
    "call_sheet": CallSheet,
    "release": Release,
    "campaign": Campaign,
    "travel_itinerary": TravelItinerary,
    "travel_segment": TravelSegment,
    "accommodation_stay": AccommodationStay,
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
            PortalDocumentSerializer(portal_documents(request.user, org), many=True).data
        )


class PlatformDocumentListView(APIView):
    permission_classes = [PlatformSuperuser]

    def get(self, request):
        return Response(
            PlatformDocumentSummarySerializer(
                filter_documents(
                    Document.objects.all()
                    .select_related("organization")
                    .prefetch_related(
                        "links__artist",
                        "links__booking",
                        "links__call_sheet",
                        "links__release",
                        "links__campaign",
                    ),
                    request,
                ),
                many=True,
            ).data
        )


class PlatformDocumentDetailView(APIView):
    permission_classes = [PlatformSuperuser]

    def get(self, request, document_id):
        return Response(
            DocumentSerializer(
                get_object_or_404(Document.objects.prefetch_related("links"), pk=document_id)
            ).data
        )


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
