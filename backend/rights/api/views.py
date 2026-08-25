from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from artists.selectors import portal_artists_for_user
from music.models import Track
from organizations.api.permissions import PlatformSuperuser
from organizations.models import Organization
from organizations.selectors import organizations_for_user
from rights.models import (
    MasterRight,
    RightsParty,
    RoyaltyAllocation,
    RoyaltyStatement,
    RoyaltyStatementLine,
    Work,
)
from rights.selectors import parties_for_user, statements_for_user, works_for_user
from rights.services import (
    add_contributor,
    add_master_right,
    add_publishing_right,
    add_statement_line,
    allocate_manual,
    archive_work,
    create_party,
    create_statement,
    create_work,
    finalize_statement,
    generate_allocations,
    link_track,
    require,
    update_manual_allocation,
    update_statement,
    void_statement,
)
from white_label.services import authenticate_api_key

from .serializers import (
    DeveloperTrackRightsSerializer,
    DeveloperWorkSerializer,
    LineSerializer,
    ManualAllocationSerializer,
    MasterSerializer,
    PartySerializer,
    PublishingSerializer,
    StatementSerializer,
    WorkSerializer,
)


def valid(call):
    try:
        return call()
    except DjangoValidationError as error:
        raise ValidationError(
            error.message_dict if hasattr(error, "message_dict") else error.messages
        ) from error


def organization_for(user, value, permission):
    organization = get_object_or_404(
        Organization.objects.filter(pk__in=organizations_for_user(user)), pk=value
    )
    require(user, organization, permission)
    return organization


def work_for(user, pk):
    return get_object_or_404(
        works_for_user(user).prefetch_related(
            "track_links__track", "contributors__party", "publishing_rights__party"
        ),
        pk=pk,
    )


def statement_for(user, pk):
    return get_object_or_404(
        statements_for_user(user).prefetch_related("lines__allocations__party"), pk=pk
    )


class WorkListCreate(APIView):
    def get(self, request):
        queryset = works_for_user(request.user).prefetch_related(
            "track_links__track", "contributors__party", "publishing_rights__party"
        )
        if request.query_params.get("organization_id"):
            organization = organization_for(
                request.user, request.query_params["organization_id"], "rights.view"
            )
            queryset = queryset.filter(organization=organization)
        if request.query_params.get("track"):
            queryset = queryset.filter(
                track_links__track_id=request.query_params["track"]
            )
        return Response(WorkSerializer(queryset[:250], many=True).data)

    def post(self, request):
        organization = organization_for(
            request.user, request.data.get("organization"), "rights.manage"
        )
        serializer = WorkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = {
            k: v
            for k, v in serializer.validated_data.items()
            if k not in ("organization",)
        }
        return Response(
            WorkSerializer(
                valid(
                    lambda: create_work(
                        actor=request.user,
                        organization=organization,
                        data=values,
                        request=request,
                    )
                )
            ).data,
            status=201,
        )


class WorkDetail(APIView):
    def get(self, request, pk):
        return Response(WorkSerializer(work_for(request.user, pk)).data)


class WorkArchive(APIView):
    def post(self, request, pk):
        return Response(
            WorkSerializer(
                valid(
                    lambda: archive_work(
                        actor=request.user,
                        work=work_for(request.user, pk),
                        request=request,
                    )
                )
            ).data
        )


class WorkTrack(APIView):
    def post(self, request, pk):
        work = work_for(request.user, pk)
        track = get_object_or_404(
            Track, pk=request.data.get("track"), organization=work.organization
        )
        relation = request.data.get("relationship_type", "primary")
        return Response(
            {
                "id": valid(
                    lambda: link_track(
                        actor=request.user,
                        work=work,
                        track=track,
                        relationship_type=relation,
                        request=request,
                    )
                ).id
            },
            status=201,
        )


class WorkContributorView(APIView):
    def post(self, request, pk):
        work = work_for(request.user, pk)
        party = get_object_or_404(
            RightsParty, pk=request.data.get("party"), organization=work.organization
        )
        values = {
            "party": party,
            "role": request.data.get("role"),
            "sequence": request.data.get("sequence", 1),
            "notes": request.data.get("notes", ""),
        }
        return Response(
            {
                "id": valid(
                    lambda: add_contributor(
                        actor=request.user, work=work, data=values, request=request
                    )
                ).id
            },
            status=201,
        )


class PublishingView(APIView):
    def post(self, request, pk):
        work = work_for(request.user, pk)
        serializer = PublishingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        return Response(
            PublishingSerializer(
                valid(
                    lambda: add_publishing_right(
                        actor=request.user, work=work, data=values, request=request
                    )
                )
            ).data,
            status=201,
        )


class PartyListCreate(APIView):
    def get(self, request):
        queryset = parties_for_user(request.user)
        if request.query_params.get("organization_id"):
            organization = organization_for(
                request.user, request.query_params["organization_id"], "rights.view"
            )
            queryset = queryset.filter(organization=organization)
        return Response(PartySerializer(queryset[:250], many=True).data)

    def post(self, request):
        organization = organization_for(
            request.user, request.data.get("organization"), "rights.manage"
        )
        serializer = PartySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = {
            k: v for k, v in serializer.validated_data.items() if k != "organization"
        }
        return Response(
            PartySerializer(
                valid(
                    lambda: create_party(
                        actor=request.user,
                        organization=organization,
                        data=values,
                        request=request,
                    )
                )
            ).data,
            status=201,
        )


class MasterListCreate(APIView):
    def get(self, request):
        organization = organization_for(
            request.user, request.query_params.get("organization_id"), "rights.view"
        )
        queryset = MasterRight.objects.filter(organization=organization)
        if request.query_params.get("track"):
            queryset = queryset.filter(track_id=request.query_params["track"])
        return Response(
            MasterSerializer(
                queryset.select_related("party", "track")[:250],
                many=True,
            ).data
        )

    def post(self, request):
        track = get_object_or_404(Track, pk=request.data.get("track"))
        serializer = MasterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = {
            k: v
            for k, v in serializer.validated_data.items()
            if k not in ("track", "organization")
        }
        return Response(
            MasterSerializer(
                valid(
                    lambda: add_master_right(
                        actor=request.user, track=track, data=values, request=request
                    )
                )
            ).data,
            status=201,
        )


class RightsOverview(APIView):
    def get(self, request):
        organization = organization_for(
            request.user, request.query_params.get("organization_id"), "rights.view"
        )
        works = Work.objects.filter(organization=organization)
        master_tracks = Track.objects.filter(
            organization=organization, master_rights__isnull=False
        ).distinct()
        incomplete_master = sum(
            1
            for track in master_tracks
            if (
                track.master_rights.aggregate(total=Sum("ownership_percentage"))[
                    "total"
                ]
                or 0
            )
            < 100
        )
        incomplete_publishing = sum(
            1
            for work in works
            if (
                work.publishing_rights.aggregate(total=Sum("ownership_percentage"))[
                    "total"
                ]
                or 0
            )
            < 100
        )
        return Response(
            {
                "works": works.count(),
                "parties": RightsParty.objects.filter(
                    organization=organization
                ).count(),
                "incomplete_master": incomplete_master,
                "incomplete_publishing": incomplete_publishing,
            }
        )


class StatementListCreate(APIView):
    def get(self, request):
        queryset = statements_for_user(request.user).prefetch_related(
            "lines__allocations__party"
        )
        if request.query_params.get("organization_id"):
            organization = organization_for(
                request.user, request.query_params["organization_id"], "royalties.view"
            )
            queryset = queryset.filter(organization=organization)
        return Response(StatementSerializer(queryset[:250], many=True).data)

    def post(self, request):
        organization = organization_for(
            request.user, request.data.get("organization"), "royalties.manage"
        )
        serializer = StatementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = {
            k: v for k, v in serializer.validated_data.items() if k != "organization"
        }
        return Response(
            StatementSerializer(
                valid(
                    lambda: create_statement(
                        actor=request.user,
                        organization=organization,
                        data=values,
                        request=request,
                    )
                )
            ).data,
            status=201,
        )


class StatementDetail(APIView):
    def get(self, request, pk):
        return Response(StatementSerializer(statement_for(request.user, pk)).data)

    def patch(self, request, pk):
        statement = statement_for(request.user, pk)
        serializer = StatementSerializer(statement, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = {
            key: value
            for key, value in serializer.validated_data.items()
            if key != "organization"
        }
        return Response(
            StatementSerializer(
                valid(
                    lambda: update_statement(
                        actor=request.user,
                        statement=statement,
                        data=values,
                        request=request,
                    )
                )
            ).data
        )


class StatementLineView(APIView):
    def post(self, request, pk):
        statement = statement_for(request.user, pk)
        serializer = LineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            LineSerializer(
                valid(
                    lambda: add_statement_line(
                        actor=request.user,
                        statement=statement,
                        data=serializer.validated_data,
                        request=request,
                    )
                )
            ).data,
            status=201,
        )


class GenerateView(APIView):
    def post(self, request, pk):
        line = get_object_or_404(
            RoyaltyStatementLine, pk=pk, statement__in=statements_for_user(request.user)
        )
        return Response(
            {
                "created": len(
                    valid(
                        lambda: generate_allocations(
                            actor=request.user, line=line, request=request
                        )
                    )
                )
            }
        )


class ManualAllocationView(APIView):
    def post(self, request, pk):
        line = get_object_or_404(
            RoyaltyStatementLine, pk=pk, statement__in=statements_for_user(request.user)
        )
        serializer = ManualAllocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        party = get_object_or_404(
            RightsParty,
            pk=serializer.validated_data["party"],
            organization=line.statement.organization,
        )
        allocation = valid(
            lambda: allocate_manual(
                actor=request.user,
                line=line,
                party=party,
                percentage=serializer.validated_data["percentage"],
                amount=serializer.validated_data["amount"],
                request=request,
            )
        )
        return Response({"id": allocation.id}, status=201)


class ManualAllocationDetail(APIView):
    def patch(self, request, pk):
        allocation = get_object_or_404(
            RoyaltyAllocation,
            pk=pk,
            statement_line__statement__in=statements_for_user(request.user),
        )
        serializer = ManualAllocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        party = get_object_or_404(
            RightsParty,
            pk=serializer.validated_data["party"],
            organization=allocation.statement_line.statement.organization,
        )
        updated = valid(
            lambda: update_manual_allocation(
                actor=request.user,
                allocation=allocation,
                party=party,
                percentage=serializer.validated_data["percentage"],
                amount=serializer.validated_data["amount"],
                request=request,
            )
        )
        return Response({"id": updated.id})


class StatementFinalize(APIView):
    def post(self, request, pk):
        return Response(
            StatementSerializer(
                valid(
                    lambda: finalize_statement(
                        actor=request.user,
                        statement=statement_for(request.user, pk),
                        request=request,
                    )
                )
            ).data
        )


class StatementVoid(APIView):
    def post(self, request, pk):
        return Response(
            StatementSerializer(
                valid(
                    lambda: void_statement(
                        actor=request.user,
                        statement=statement_for(request.user, pk),
                        reason=request.data.get("reason", ""),
                        request=request,
                    )
                )
            ).data
        )


class PlatformWorks(WorkListCreate):
    permission_classes = (PlatformSuperuser,)


class PlatformStatements(StatementListCreate):
    permission_classes = (PlatformSuperuser,)


class ArtistRights(APIView):
    def get(self, request):
        artist_ids = portal_artists_for_user(request.user).values_list("id", flat=True)
        parties = RightsParty.objects.filter(linked_artist_id__in=artist_ids)
        allocations = []
        for party in parties:
            allocations.extend(
                [
                    {
                        "party": party.display_name,
                        "statement": row.statement_line.statement.statement_reference,
                        "currency": row.statement_line.statement.currency,
                        "amount": str(row.amount),
                    }
                    for row in party.royalty_allocations.filter(
                        statement_line__statement__status=RoyaltyStatement.Status.FINALIZED
                    ).select_related("statement_line__statement")
                ]
            )
        return Response(
            {
                "parties": [
                    {"id": p.id, "display_name": p.display_name} for p in parties
                ],
                "allocations": allocations,
            }
        )


class DeveloperWorks(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        key = authenticate_api_key(
            request.headers.get("Authorization", "")[7:], "rights.read"
        )
        queryset = Work.objects.filter(
            organization=key.client.organization
        ).prefetch_related("track_links", "contributors__party")
        return Response(DeveloperWorkSerializer(queryset[:250], many=True).data)


class DeveloperTracks(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        key = authenticate_api_key(
            request.headers.get("Authorization", "")[7:], "rights.read"
        )
        queryset = Track.objects.filter(
            organization=key.client.organization
        ).prefetch_related("master_rights__party", "work_links__work")
        return Response(DeveloperTrackRightsSerializer(queryset[:250], many=True).data)
