from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from artists.models import Artist, ArtistPortalLink, ArtistTeamAssignment, ArtistToolkit
from artists.selectors import artist_activity, artists_for_user, portal_artists_for_user
from artists.services import (
    assign_team_member,
    create_artist,
    link_portal_user,
    require_artist_permission,
    unlink_portal_user,
    update_artist,
    update_team_assignment,
)
from bookings.models import Booking
from callsheets.models import CallSheetVersion
from campaigns.models import Campaign
from documents.selectors import documents_for_user
from music.models import Release, Track
from organizations.api.permissions import PlatformSuperuser
from organizations.models import Membership, Organization
from organizations.selectors import organizations_for_user
from rights.models import Work
from users.models import User
from white_label.services import authenticate_api_key

from .serializers import (
    ArtistSerializer,
    ArtistToolkitSerializer,
    ArtistWriteSerializer,
    DeveloperArtistSerializer,
    PortalArtistSerializer,
    PortalLinkCreateSerializer,
    PortalLinkSerializer,
    TeamAssignmentCreateSerializer,
    TeamAssignmentSerializer,
)


def artist_queryset():
    active_team = ArtistTeamAssignment.objects.filter(is_active=True).select_related(
        "membership__user"
    )
    return (
        Artist.objects.select_related("organization")
        .annotate(
            team_count=Count(
                "team_assignments",
                filter=Q(team_assignments__is_active=True),
                distinct=True,
            ),
            portal_user_count=Count(
                "portal_links", filter=Q(portal_links__is_active=True), distinct=True
            ),
        )
        .prefetch_related(
            Prefetch("team_assignments", queryset=active_team, to_attr="prefetched_team")
        )
    )


def scoped_organization(user, organization_id):
    return get_object_or_404(
        Organization.objects.filter(pk__in=organizations_for_user(user).values("pk")),
        pk=organization_id,
    )


def scoped_artist(user, artist_id):
    return get_object_or_404(
        artist_queryset().filter(pk__in=artists_for_user(user).values("pk")),
        pk=artist_id,
    )


def validation_call(callable_):
    try:
        return callable_()
    except DjangoValidationError as error:
        detail = error.message_dict if hasattr(error, "message_dict") else error.messages
        raise ValidationError(detail) from error


def activity_data(artist):
    return [
        {
            "id": event.id,
            "action": event.action,
            "description": event.description,
            "actor": event.actor.email if event.actor else None,
            "created_at": event.created_at,
        }
        for event in artist_activity(artist)
    ]


class ArtistListView(APIView):
    def get(self, request):
        organization = scoped_organization(
            request.user, request.query_params.get("organization_id")
        )
        require_artist_permission(request.user, organization, "artist.view")
        artists = artist_queryset().filter(organization=organization)
        return Response(ArtistSerializer(artists, many=True).data)

    def post(self, request):
        organization = scoped_organization(request.user, request.data.get("organization_id"))
        serializer = ArtistWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        artist = validation_call(
            lambda: create_artist(
                actor=request.user,
                organization=organization,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(
            ArtistSerializer(artist_queryset().get(pk=artist.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class ArtistDetailView(APIView):
    def get(self, request, artist_id):
        artist = scoped_artist(request.user, artist_id)
        require_artist_permission(request.user, artist.organization, "artist.view")
        data = ArtistSerializer(artist).data
        data["team"] = TeamAssignmentSerializer(
            artist.team_assignments.select_related("membership__user"), many=True
        ).data
        data["portal_links"] = PortalLinkSerializer(
            artist.portal_links.select_related("user"), many=True
        ).data
        data["activity"] = activity_data(artist)
        return Response(data)

    def patch(self, request, artist_id):
        artist = scoped_artist(request.user, artist_id)
        serializer = ArtistWriteSerializer(artist, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        artist = validation_call(
            lambda: update_artist(
                actor=request.user,
                artist=artist,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(ArtistSerializer(artist_queryset().get(pk=artist.pk)).data)


class Artist360View(APIView):
    def get(self, request, artist_id):
        artist = scoped_artist(request.user, artist_id)
        require_artist_permission(request.user, artist.organization, "artist.view")
        bookings = (
            Booking.objects.filter(organization=artist.organization, artist=artist)
            .select_related("venue", "promoter")
            .order_by("-event_date")[:12]
        )
        releases = Release.objects.filter(primary_artist=artist).order_by("-planned_release_date")[
            :8
        ]
        tracks = Track.objects.filter(primary_artist=artist).order_by("title")[:12]
        campaigns = Campaign.objects.filter(artist=artist).order_by("-updated_at")[:8]
        works = Work.objects.filter(track_links__track__primary_artist=artist).distinct()
        documents = (
            documents_for_user(request.user, artist.organization)
            .filter(links__artist=artist)
            .distinct()[:8]
        )
        call_sheets = CallSheetVersion.objects.filter(
            call_sheet__booking__artist=artist,
            status=CallSheetVersion.Status.PUBLISHED,
        ).order_by("-event_date")[:6]
        tracks_with_master_rights = Track.objects.filter(
            primary_artist=artist, master_rights__isnull=False
        ).distinct()
        master_incomplete = (
            tracks_with_master_rights.annotate(
                allocated_percentage=Sum("master_rights__ownership_percentage")
            )
            .filter(allocated_percentage__lt=100)
            .count()
        )
        publishing_incomplete = (
            works.filter(publishing_rights__isnull=False)
            .annotate(allocated_percentage=Sum("publishing_rights__ownership_percentage"))
            .filter(allocated_percentage__lt=100)
            .count()
        )
        return Response(
            {
                "bookings": [
                    {
                        "id": item.id,
                        "reference": item.reference,
                        "date": item.event_date,
                        "venue": item.venue.name if item.venue else item.venue_name_snapshot,
                        "promoter": item.promoter.name
                        if item.promoter
                        else item.promoter_name_snapshot,
                        "status": item.status,
                    }
                    for item in bookings
                ],
                "call_sheets": [
                    {"id": item.id, "title": item.title, "date": item.event_date}
                    for item in call_sheets
                ],
                "releases": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "date": item.planned_release_date,
                        "status": item.status,
                        "artwork_url": item.artwork_url,
                        "upc_ean": item.upc_ean,
                        "public_url": item.public_url,
                    }
                    for item in releases
                ],
                "tracks": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "status": item.status,
                        "isrc": item.isrc,
                        "artwork_url": item.artwork_url,
                    }
                    for item in tracks
                ],
                "campaigns": [
                    {"id": item.id, "name": item.name, "status": item.status} for item in campaigns
                ],
                "documents": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "type": item.document_type,
                        "content_type": item.content_type,
                        "original_filename": item.original_filename,
                        "external_url": item.external_url if item.external_url.startswith("https://") else "",
                    }
                    for item in documents
                ],
                "rights": {
                    "works": works.count(),
                    "tracks_with_master_rights": tracks_with_master_rights.count(),
                    "incomplete_master_splits": master_incomplete,
                    "incomplete_publishing_splits": publishing_incomplete,
                },
            }
        )


class ArtistToolkitView(APIView):
    def get(self, request, artist_id):
        artist = scoped_artist(request.user, artist_id)
        require_artist_permission(request.user, artist.organization, "artist.view")
        toolkit = ArtistToolkit.objects.filter(artist=artist).first()
        return Response(ArtistToolkitSerializer(toolkit).data if toolkit else {
            "short_bio": "",
            "long_bio": "",
            "rate_card": "",
            "stats_summary": "",
        })

    def patch(self, request, artist_id):
        artist = scoped_artist(request.user, artist_id)
        require_artist_permission(request.user, artist.organization, "artist.manage")
        toolkit, _ = ArtistToolkit.objects.get_or_create(artist=artist)
        serializer = ArtistToolkitSerializer(toolkit, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        toolkit = serializer.save()
        from audit.services import record_event

        record_event(actor=request.user, organization=artist.organization, action="artist.toolkit_updated", resource=toolkit, description=f"Updated toolkit for {artist.stage_name}.", request=request)
        return Response(ArtistToolkitSerializer(toolkit).data)


class ArtistTeamView(APIView):
    def get(self, request, artist_id):
        artist = scoped_artist(request.user, artist_id)
        require_artist_permission(request.user, artist.organization, "artist.view")
        assignments = artist.team_assignments.select_related("membership__user")
        return Response(TeamAssignmentSerializer(assignments, many=True).data)

    def post(self, request, artist_id):
        artist = scoped_artist(request.user, artist_id)
        serializer = TeamAssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = get_object_or_404(
            Membership.objects.select_related("organization", "user"),
            pk=serializer.validated_data.pop("membership_id"),
            organization=artist.organization,
        )
        assignment = validation_call(
            lambda: assign_team_member(
                actor=request.user,
                artist=artist,
                membership=membership,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(TeamAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)


class ArtistTeamDetailView(APIView):
    def patch(self, request, artist_id, assignment_id):
        artist = scoped_artist(request.user, artist_id)
        assignment = get_object_or_404(ArtistTeamAssignment, pk=assignment_id, artist=artist)
        serializer = TeamAssignmentSerializer(assignment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        assignment = validation_call(
            lambda: update_team_assignment(
                actor=request.user,
                assignment=assignment,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(TeamAssignmentSerializer(assignment).data)


class ArtistPortalLinksView(APIView):
    def get(self, request, artist_id):
        artist = scoped_artist(request.user, artist_id)
        require_artist_permission(request.user, artist.organization, "artist.team.manage")
        return Response(
            PortalLinkSerializer(artist.portal_links.select_related("user"), many=True).data
        )

    def post(self, request, artist_id):
        artist = scoped_artist(request.user, artist_id)
        serializer = PortalLinkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_object_or_404(User, pk=serializer.validated_data["user_id"])
        link = validation_call(
            lambda: link_portal_user(
                actor=request.user,
                artist=artist,
                user=user,
                relationship=serializer.validated_data["relationship"],
                request=request,
            )
        )
        return Response(PortalLinkSerializer(link).data, status=status.HTTP_201_CREATED)


class ArtistPortalLinkDetailView(APIView):
    def post(self, request, artist_id, link_id):
        artist = scoped_artist(request.user, artist_id)
        link = get_object_or_404(ArtistPortalLink, pk=link_id, artist=artist)
        unlink_portal_user(actor=request.user, link=link, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ArtistPortalView(APIView):
    def get(self, request):
        artists = portal_artists_for_user(request.user).prefetch_related(
            "team_assignments__membership__user"
        )
        return Response(PortalArtistSerializer(artists, many=True).data)


class PlatformArtistListView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        return Response(ArtistSerializer(artist_queryset(), many=True).data)

    def post(self, request):
        organization = get_object_or_404(Organization, pk=request.data.get("organization_id"))
        serializer = ArtistWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        artist = validation_call(
            lambda: create_artist(
                actor=request.user,
                organization=organization,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(
            ArtistSerializer(artist_queryset().get(pk=artist.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class PlatformArtistDetailView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request, artist_id):
        artist = get_object_or_404(artist_queryset(), pk=artist_id)
        data = ArtistSerializer(artist).data
        data["team"] = TeamAssignmentSerializer(
            artist.team_assignments.select_related("membership__user"), many=True
        ).data
        data["portal_links"] = PortalLinkSerializer(
            artist.portal_links.select_related("user"), many=True
        ).data
        data["activity"] = activity_data(artist)
        return Response(data)

    def patch(self, request, artist_id):
        artist = get_object_or_404(Artist, pk=artist_id)
        serializer = ArtistWriteSerializer(artist, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        artist = validation_call(
            lambda: update_artist(
                actor=request.user,
                artist=artist,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(ArtistSerializer(artist_queryset().get(pk=artist.pk)).data)


class DeveloperArtistListView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise PermissionDenied("Invalid API credentials.")
        key = authenticate_api_key(header[7:], required_scope="artist.read")
        artists = Artist.objects.filter(organization=key.client.organization).order_by("stage_name")
        return Response(DeveloperArtistSerializer(artists, many=True).data)
