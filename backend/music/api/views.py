from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from artists.models import Artist
from contacts.models import Contact
from documents.file_validation import validate_upload
from documents.models import Document
from documents.services import upload_document
from music.export_services import PUBLISHING_HEADERS, csv_response, pdf_response, publishing_rows
from music.import_services import import_release_workbook
from music.models import MusicCredit, Release, ReleaseLink, ReleaseTrack, Track
from music.selectors import (
    music_activity,
    portal_releases_for_user,
    portal_tracks_for_user,
    releases_for_user,
    tracks_for_user,
)
from music.services import (
    add_release_track,
    allowed_release_transitions,
    create_credit,
    create_link,
    create_release,
    create_track,
    prepare_release,
    remove_credit,
    remove_link,
    remove_release_track,
    require_music_permission,
    transition_release,
    update_credit,
    update_link,
    update_release,
    update_release_track,
    update_track,
)
from organizations.api.permissions import PlatformSuperuser
from organizations.models import Organization
from organizations.selectors import organizations_for_user
from white_label.services import authenticate_api_key

from .serializers import (
    CreditSerializer,
    DeveloperReleaseSerializer,
    DeveloperTrackSerializer,
    ReleaseDetailSerializer,
    ReleaseLinkSerializer,
    ReleasePipelineSerializer,
    ReleaseSummarySerializer,
    ReleaseTrackSerializer,
    ReleaseWriteSerializer,
    StatusSerializer,
    TrackDetailSerializer,
    TrackSummarySerializer,
    TrackWriteSerializer,
)


def validated(call):
    try:
        return call()
    except DjangoValidationError as error:
        detail = error.message_dict if hasattr(error, "message_dict") else error.messages
        raise ValidationError(detail) from error


def scoped_organization(user, organization_id):
    return get_object_or_404(
        Organization.objects.filter(pk__in=organizations_for_user(user).values("pk")),
        pk=organization_id,
    )


def release_queryset():
    return (
        Release.objects.select_related("organization", "primary_artist")
        .prefetch_related("tasks", "campaigns")
        .annotate(track_count=Count("track_placements"))
    )


def track_queryset():
    return Track.objects.select_related("organization", "primary_artist", "audio_document").annotate(
        releases_count=Count("release_placements")
    )


def scoped_release(user, release_id):
    return get_object_or_404(
        release_queryset().filter(pk__in=releases_for_user(user).values("pk")), pk=release_id
    )


def scoped_track(user, track_id):
    return get_object_or_404(
        track_queryset().filter(pk__in=tracks_for_user(user).values("pk")), pk=track_id
    )


def activity(resource):
    return [
        {
            "id": event.id,
            "action": event.action,
            "description": event.description,
            "actor": event.actor.email if event.actor else None,
            "created_at": event.created_at,
        }
        for event in music_activity(resource)
    ]


def release_detail(release):
    release.allowed_transitions = allowed_release_transitions(release)
    release.activity = activity(release)
    return ReleaseDetailSerializer(release).data


def track_detail(track):
    track.activity = activity(track)
    return TrackDetailSerializer(track).data


def _release_metadata_rows(release):
    placements = release.track_placements.select_related("track").order_by(
        "sequence", "disc_number", "track_number"
    )
    for placement in placements:
        track = placement.track
        yield [
            release.title,
            release.primary_artist.stage_name,
            release.planned_release_date,
            release.upc_ean,
            release.catalog_number,
            release.label_name,
            release.distributor_name,
            placement.disc_number,
            placement.track_number,
            track.title,
            track.version_title,
            track.isrc,
            track.duration_seconds,
            track.release_year,
            track.language,
            track.genre,
            track.subgenre,
            track.explicit_content,
            track.artwork_url,
            track.audio_preview_url,
        ]


METADATA_HEADERS = (
    "Release title", "Primary artist", "Release date", "UPC / EAN", "Catalog number",
    "Label", "Distributor", "Disc number", "Track number", "Track title",
    "Version title", "ISRC", "Duration seconds", "Release year", "Language",
    "Genre", "Subgenre", "Explicit", "Artwork URL", "Audio preview URL",
)


class ReleaseMetadataExportView(APIView):
    def get(self, request, release_id):
        release = scoped_release(request.user, release_id)
        require_music_permission(request.user, release.organization, "music.view")
        return csv_response(
            f"{release.slug}-metadata.csv", METADATA_HEADERS, list(_release_metadata_rows(release))
        )


class TrackPublishingSplitExportView(APIView):
    def get(self, request, track_id):
        track = scoped_track(request.user, track_id)
        require_music_permission(request.user, track.organization, "music.view")
        rows = publishing_rows(track)
        if request.query_params.get("format") == "pdf" or request.path.endswith(".pdf"):
            lines = [
                f"Artist: {track.primary_artist.stage_name}",
                f"Track: {track.title}",
                f"ISRC: {track.isrc or 'Not set'}",
                "",
            ]
            lines.extend(" | ".join(str(value or "") for value in row) for row in rows)
            return pdf_response(
                f"{track.slug}-publishing-split.pdf",
                f"Publishing split sheet - {track.title}",
                lines,
            )
        return csv_response(f"{track.slug}-publishing-split.csv", PUBLISHING_HEADERS, rows)


def filters(queryset, request, track=False):
    search = request.query_params.get("search", "").strip()
    if search:
        lookup = Q(title__icontains=search) | Q(primary_artist__stage_name__icontains=search)
        lookup |= Q(isrc__icontains=search) if track else Q(upc_ean__icontains=search)
        queryset = queryset.filter(lookup)
    for parameter, field in {
        "artist": "primary_artist_id",
        "status": "status",
        "type": "release_type",
        "organization_id": "organization_id",
    }.items():
        if request.query_params.get(parameter) and (not track or parameter != "type"):
            queryset = queryset.filter(**{field: request.query_params[parameter]})
    if not track and request.query_params.get("date_from"):
        queryset = queryset.filter(planned_release_date__gte=request.query_params["date_from"])
    if not track and request.query_params.get("date_to"):
        queryset = queryset.filter(planned_release_date__lte=request.query_params["date_to"])
    return queryset


class ReleaseListView(APIView):
    def get(self, request):
        organization = scoped_organization(
            request.user, request.query_params.get("organization_id")
        )
        require_music_permission(request.user, organization, "music.view")
        return Response(
            ReleasePipelineSerializer(
                filters(release_queryset().filter(organization=organization), request), many=True
            ).data
        )

    def post(self, request):
        organization = scoped_organization(request.user, request.data.get("organization_id"))
        serializer = ReleaseWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        artist = get_object_or_404(
            Artist, pk=data.pop("primary_artist_id"), organization=organization
        )
        release = validated(
            lambda: create_release(
                actor=request.user,
                organization=organization,
                data={**data, "primary_artist": artist},
                request=request,
            )
        )
        return Response(release_detail(release), status=status.HTTP_201_CREATED)


class ReleaseDetailView(APIView):
    def get(self, request, release_id):
        release = scoped_release(request.user, release_id)
        require_music_permission(request.user, release.organization, "music.view")
        return Response(release_detail(release))

    def patch(self, request, release_id):
        release = scoped_release(request.user, release_id)
        if "status" in request.data:
            raise ValidationError({"status": "Use the status endpoint."})
        serializer = ReleaseWriteSerializer(release, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if "primary_artist_id" in data:
            data["primary_artist"] = get_object_or_404(
                Artist, pk=data.pop("primary_artist_id"), organization=release.organization
            )
        release = validated(
            lambda: update_release(actor=request.user, release=release, data=data, request=request)
        )
        return Response(release_detail(release))


def release_readiness(release):
    placements = list(release.track_placements.select_related("track"))
    tracks = [placement.track for placement in placements]
    release_href = f"/workspace/music/releases/{release.id}"
    checks = {
        "tracks": (bool(tracks), release_href),
        "metadata": (
            all(track.isrc and track.genre and track.language for track in tracks),
            "/workspace/music/metadata",
        ),
        "identifiers": (bool(release.upc_ean), release_href),
        "credits": (
            bool(release.credits.exists()) or all(track.credits.exists() for track in tracks),
            release_href,
        ),
        "rights": (
            all(track.work_links.exists() for track in tracks) if tracks else False,
            "/workspace/rights",
        ),
        "masters": (all(bool(track.audio_preview_url) for track in tracks), release_href),
        "artwork": (bool(release.artwork_url), release_href),
        "distribution": (
            bool(release.distributor_name and release.upc_ean),
            "/workspace/music/distribution",
        ),
        "campaign": (release.campaigns.exists(), "/workspace/campaigns"),
    }
    return {
        key: {"status": "ready" if complete else "needs_attention", "href": href}
        for key, (complete, href) in checks.items()
    }


def release_next_action(release, readiness):
    actions = (
        ("tracks", "Add tracks", f"/workspace/music/releases/{release.id}"),
        ("metadata", "Complete metadata", "/workspace/music/metadata"),
        ("rights", "Review rights", "/workspace/rights"),
        ("masters", "Add master reference", f"/workspace/music/releases/{release.id}"),
        ("artwork", "Add artwork", f"/workspace/music/releases/{release.id}"),
        ("distribution", "Prepare distribution", "/workspace/music/distribution"),
        ("campaign", "Create campaign", "/workspace/campaigns/new"),
    )
    for key, label, href in actions:
        if readiness[key]["status"] != "ready":
            return {"key": key, "label": label, "href": href}
    return {
        "key": "review",
        "label": "Review release readiness",
        "href": f"/workspace/music/releases/{release.id}",
    }


class ReleaseReadinessView(APIView):
    def get(self, request, release_id):
        release = scoped_release(request.user, release_id)
        require_music_permission(request.user, release.organization, "music.view")
        readiness = release_readiness(release)
        return Response(
            {
                "release_id": release.id,
                "readiness": readiness,
                "next_action": release_next_action(release, readiness),
            }
        )


class ReleasePrepareView(APIView):
    def post(self, request, release_id):
        release = scoped_release(request.user, release_id)
        tasks = validated(
            lambda: prepare_release(actor=request.user, release=release, request=request)
        )
        return Response(
            {
                "release_id": release.id,
                "tasks": [
                    {"id": task.id, "title": task.title, "status": task.status}
                    for task in tasks
                ],
            }
        )


class ReleaseStatusView(APIView):
    def post(self, request, release_id):
        release = scoped_release(request.user, release_id)
        serializer = StatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        release = validated(
            lambda: transition_release(
                actor=request.user, release=release, request=request, **serializer.validated_data
            )
        )
        return Response(release_detail(release))


class TrackListView(APIView):
    def get(self, request):
        organization = scoped_organization(
            request.user, request.query_params.get("organization_id")
        )
        require_music_permission(request.user, organization, "music.view")
        return Response(
            TrackSummarySerializer(
                filters(track_queryset().filter(organization=organization), request, track=True),
                many=True,
            ).data
        )

    def post(self, request):
        organization = scoped_organization(request.user, request.data.get("organization_id"))
        serializer = TrackWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        artist = get_object_or_404(
            Artist, pk=data.pop("primary_artist_id"), organization=organization
        )
        track = validated(
            lambda: create_track(
                actor=request.user,
                organization=organization,
                data={**data, "primary_artist": artist},
                request=request,
            )
        )
        return Response(track_detail(track), status=status.HTTP_201_CREATED)


class TrackDetailView(APIView):
    def get(self, request, track_id):
        track = scoped_track(request.user, track_id)
        require_music_permission(request.user, track.organization, "music.view")
        return Response(track_detail(track))

    def patch(self, request, track_id):
        track = scoped_track(request.user, track_id)
        serializer = TrackWriteSerializer(track, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if "primary_artist_id" in data:
            data["primary_artist"] = get_object_or_404(
                Artist, pk=data.pop("primary_artist_id"), organization=track.organization
            )
        track = validated(
            lambda: update_track(actor=request.user, track=track, data=data, request=request)
        )
        return Response(track_detail(track))


class TrackAudioUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, track_id):
        track = scoped_track(request.user, track_id)
        require_music_permission(request.user, track.organization, "music.track.manage")
        file = request.FILES.get("file")
        if not file:
            raise ValidationError({"file": "Choose an audio file to upload."})
        try:
            metadata = validate_upload(file, document_type=Document.Type.MUSIC)
            if not metadata["detected_content_type"].startswith("audio/"):
                raise ValidationError({"file": "Only audio files can be attached to a track."})
            document = upload_document(
                actor=request.user,
                organization=track.organization,
                file=file,
                request=request,
                title=f"{track.title} audio",
                document_type=Document.Type.MUSIC,
                visibility=Document.Visibility.PRIVATE,
            )
            track = validated(
                lambda: update_track(
                    actor=request.user,
                    track=track,
                    data={"audio_document": document, "audio_preview_url": ""},
                    request=request,
                )
            )
        except (DjangoValidationError, PermissionError) as error:
            detail = getattr(error, "message_dict", None) or getattr(error, "messages", None) or str(error)
            raise ValidationError(detail) from error
        return Response(track_detail(track), status=status.HTTP_201_CREATED)


class ReleaseTracksView(APIView):
    def post(self, request, release_id):
        release = scoped_release(request.user, release_id)
        serializer = ReleaseTrackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        track = get_object_or_404(Track, pk=data.pop("track_id"), organization=release.organization)
        placement = validated(
            lambda: add_release_track(
                actor=request.user, release=release, track=track, data=data, request=request
            )
        )
        return Response(ReleaseTrackSerializer(placement).data, status=status.HTTP_201_CREATED)


class ReleaseTrackDetailView(APIView):
    def patch(self, request, release_id, placement_id):
        release = scoped_release(request.user, release_id)
        placement = get_object_or_404(ReleaseTrack, pk=placement_id, release=release)
        serializer = ReleaseTrackSerializer(placement, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("track_id", None)
        placement = validated(
            lambda: update_release_track(
                actor=request.user, placement=placement, data=data, request=request
            )
        )
        return Response(ReleaseTrackSerializer(placement).data)

    def delete(self, request, release_id, placement_id):
        release = scoped_release(request.user, release_id)
        placement = get_object_or_404(ReleaseTrack, pk=placement_id, release=release)
        validated(
            lambda: remove_release_track(actor=request.user, placement=placement, request=request)
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


def credit_data(data, organization):
    if "linked_artist_id" in data:
        linked_artist_id = data.pop("linked_artist_id")
        data["linked_artist"] = (
            get_object_or_404(Artist, pk=linked_artist_id, organization=organization)
            if linked_artist_id
            else None
        )
    if "linked_contact_id" in data:
        linked_contact_id = data.pop("linked_contact_id")
        data["linked_contact"] = (
            get_object_or_404(Contact, pk=linked_contact_id, organization=organization)
            if linked_contact_id
            else None
        )
    return data


class CreditListView(APIView):
    resource_type = None

    def resource(self, user, resource_id):
        return (
            scoped_release(user, resource_id)
            if self.resource_type == "release"
            else scoped_track(user, resource_id)
        )

    def post(self, request, resource_id):
        resource = self.resource(request.user, resource_id)
        serializer = CreditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = credit_data(serializer.validated_data, resource.organization)
        data[self.resource_type] = resource
        credit = validated(
            lambda: create_credit(
                actor=request.user,
                organization=resource.organization,
                data=data,
                resource=resource,
                request=request,
            )
        )
        return Response(CreditSerializer(credit).data, status=status.HTTP_201_CREATED)


class CreditDetailView(APIView):
    resource_type = None

    def objects(self, user, resource_id, credit_id):
        resource = (
            scoped_release(user, resource_id)
            if self.resource_type == "release"
            else scoped_track(user, resource_id)
        )
        return resource, get_object_or_404(
            MusicCredit, pk=credit_id, **{self.resource_type: resource}
        )

    def patch(self, request, resource_id, credit_id):
        resource, credit = self.objects(request.user, resource_id, credit_id)
        serializer = CreditSerializer(credit, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = credit_data(serializer.validated_data, resource.organization)
        credit = validated(
            lambda: update_credit(
                actor=request.user, credit=credit, data=data, resource=resource, request=request
            )
        )
        return Response(CreditSerializer(credit).data)

    def delete(self, request, resource_id, credit_id):
        resource, credit = self.objects(request.user, resource_id, credit_id)
        validated(
            lambda: remove_credit(
                actor=request.user, credit=credit, resource=resource, request=request
            )
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class LinkListView(APIView):
    def post(self, request, release_id):
        release = scoped_release(request.user, release_id)
        serializer = ReleaseLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = validated(
            lambda: create_link(
                actor=request.user, release=release, data=serializer.validated_data, request=request
            )
        )
        return Response(ReleaseLinkSerializer(link).data, status=status.HTTP_201_CREATED)


class LinkDetailView(APIView):
    def objects(self, user, release_id, link_id):
        release = scoped_release(user, release_id)
        return release, get_object_or_404(ReleaseLink, pk=link_id, release=release)

    def patch(self, request, release_id, link_id):
        _, link = self.objects(request.user, release_id, link_id)
        serializer = ReleaseLinkSerializer(link, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        link = validated(
            lambda: update_link(
                actor=request.user, link=link, data=serializer.validated_data, request=request
            )
        )
        return Response(ReleaseLinkSerializer(link).data)

    def delete(self, request, release_id, link_id):
        _, link = self.objects(request.user, release_id, link_id)
        validated(lambda: remove_link(actor=request.user, link=link, request=request))
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlatformReleaseListView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        return Response(
            ReleasePipelineSerializer(filters(release_queryset(), request), many=True).data
        )


class PlatformReleaseDetailView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request, release_id):
        return Response(release_detail(get_object_or_404(release_queryset(), pk=release_id)))


class PlatformTrackListView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        return Response(
            TrackSummarySerializer(filters(track_queryset(), request, track=True), many=True).data
        )


class PlatformTrackDetailView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request, track_id):
        return Response(track_detail(get_object_or_404(track_queryset(), pk=track_id)))


class ArtistPortalMusicView(APIView):
    def get(self, request):
        releases = portal_releases_for_user(request.user).select_related("primary_artist")
        tracks = (
            portal_tracks_for_user(request.user)
            .select_related("primary_artist")
            .annotate(releases_count=Count("release_placements"))
        )
        return Response(
            {
                "releases": ReleaseSummarySerializer(
                    releases.annotate(track_count=Count("track_placements")), many=True
                ).data,
                "tracks": TrackSummarySerializer(tracks, many=True).data,
            }
        )


class DeveloperMusicView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    model = None

    def get(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise PermissionDenied("Invalid API credentials.")
        key = authenticate_api_key(header[7:], required_scope="music.read")
        if self.model is Release:
            queryset = Release.objects.filter(organization=key.client.organization).select_related(
                "primary_artist"
            )
            return Response(DeveloperReleaseSerializer(queryset, many=True).data)
        queryset = Track.objects.filter(organization=key.client.organization).select_related(
            "primary_artist"
        )
        return Response(DeveloperTrackSerializer(queryset, many=True).data)


class ReleaseWorkbookImportView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        organization = scoped_organization(request.user, request.data.get("organization_id"))
        require_music_permission(request.user, organization, "music.release.manage")
        artist = get_object_or_404(
            Artist, pk=request.data.get("primary_artist_id"), organization=organization
        )
        upload = request.FILES.get("workbook")
        if not upload:
            raise ValidationError({"workbook": "Upload the XLSX workbook."})
        title = (request.data.get("title") or "Ts & Cs Apply").strip()
        raw_date = (request.data.get("release_date") or "2026-09-01").strip()
        try:
            release_date = date.fromisoformat(raw_date)
        except ValueError as error:
            raise ValidationError({"release_date": "Use YYYY-MM-DD."}) from error
        try:
            release, imported = import_release_workbook(
                actor=request.user, organization=organization, artist=artist,
                upload=upload, title=title, release_date=release_date, request=request,
            )
        except DjangoValidationError as error:
            detail = error.message_dict if hasattr(error, "message_dict") else error.messages
            raise ValidationError(detail) from error
        return Response(
            {"release": release_detail(release), "tracks_imported": imported},
            status=status.HTTP_201_CREATED,
        )
