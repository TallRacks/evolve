from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import record_event
from organizations.api.permissions import PlatformSuperuser
from organizations.models import Organization
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from travel.models import (
    AccommodationRoomAssignment,
    AccommodationStay,
    ItineraryTraveller,
    TravelSegment,
    TravelSegmentTraveller,
)
from travel.selectors import (
    artist_itineraries_for_user,
    itineraries_for_user,
    itinerary_activity,
    itinerary_queryset,
)
from travel.services import (
    SEGMENT_TRANSITIONS,
    STAY_TRANSITIONS,
    create_child,
    create_itinerary,
    remove_child,
    reorder_segment,
    transition_child,
    transition_itinerary,
    update_child,
    update_itinerary,
)
from white_label.services import authenticate_api_key

from .serializers import (
    ArtistItinerarySerializer,
    DeveloperItinerarySerializer,
    ItineraryDetailSerializer,
    ItineraryListSerializer,
    ItineraryWriteSerializer,
    ReorderSerializer,
    RoomSerializer,
    SegmentSerializer,
    SegmentTravellerSerializer,
    StatusSerializer,
    StaySerializer,
    TravellerSerializer,
)


def validation(call):
    try:
        return call()
    except DjangoValidationError as error:
        detail = error.message_dict if hasattr(error, "message_dict") else error.messages
        raise ValidationError(detail) from error


def scoped_organization(user, value):
    return get_object_or_404(
        Organization.objects.filter(pk__in=organizations_for_user(user).values("pk")), pk=value
    )


def scoped_itinerary(user, pk):
    return get_object_or_404(itineraries_for_user(user), pk=pk)


def require(user, organization, permission="travel.view"):
    if not user_has_organization_permission(user, organization, permission):
        raise PermissionDenied("You do not have permission to access Travel for this organization.")


def detail(item, user):
    activity = [
        {
            "id": row.id,
            "action": row.action,
            "description": row.description,
            "actor": row.actor.email if row.actor else None,
            "created_at": row.created_at,
        }
        for row in itinerary_activity(item)
    ]
    return ItineraryDetailSerializer(
        item,
        context={
            "activity": activity,
            "include_private": user_has_organization_permission(
                user, item.organization, "travel.private_contact.view"
            ),
        },
    ).data


class ItineraryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization = scoped_organization(
            request.user, request.query_params.get("organization_id")
        )
        require(request.user, organization)
        rows = (
            itineraries_for_user(request.user)
            .filter(organization=organization)
            .annotate(
                traveller_count=Count(
                    "travellers", filter=Q(travellers__is_active=True), distinct=True
                )
            )
            .order_by("starts_at", "title")
        )
        q = request.query_params.get("q", "").strip()
        artist = request.query_params.get("artist_id")
        booking = request.query_params.get("booking_id")
        state = request.query_params.get("status")
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        if q:
            rows = rows.filter(
                Q(title__icontains=q)
                | Q(artist__stage_name__icontains=q)
                | Q(booking__reference__icontains=q)
            )
        if artist:
            rows = rows.filter(artist_id=artist)
        if booking:
            rows = rows.filter(booking_id=booking)
        if state:
            rows = rows.filter(status=state)
        if start:
            parsed_start = parse_datetime(start)
            if parsed_start is None:
                raise ValidationError({"start": "Enter a valid ISO 8601 datetime."})
            rows = rows.filter(ends_at__gte=parsed_start)
        if end:
            parsed_end = parse_datetime(end)
            if parsed_end is None:
                raise ValidationError({"end": "Enter a valid ISO 8601 datetime."})
            rows = rows.filter(starts_at__lte=parsed_end)
        count = rows.count()
        try:
            offset = max(int(request.query_params.get("offset", 0)), 0)
        except (TypeError, ValueError) as error:
            raise ValidationError({"offset": "Enter a valid integer."}) from error
        rows = rows[offset : offset + 50]
        return Response({"count": count, "results": ItineraryListSerializer(rows, many=True).data})

    def post(self, request):
        organization = scoped_organization(request.user, request.data.get("organization_id"))
        serializer = ItineraryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = validation(
            lambda: create_itinerary(
                actor=request.user,
                organization=organization,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(detail(item, request.user), status=status.HTTP_201_CREATED)


class ItineraryDetailView(APIView):
    def get(self, request, itinerary_id):
        item = scoped_itinerary(request.user, itinerary_id)
        require(request.user, item.organization)
        return Response(detail(item, request.user))

    def patch(self, request, itinerary_id):
        item = scoped_itinerary(request.user, itinerary_id)
        serializer = ItineraryWriteSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        item = validation(
            lambda: update_itinerary(
                item, actor=request.user, data=serializer.validated_data, request=request
            )
        )
        return Response(detail(item, request.user))


class ItineraryStatusView(APIView):
    def post(self, request, itinerary_id):
        item = scoped_itinerary(request.user, itinerary_id)
        serializer = StatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = validation(
            lambda: transition_itinerary(
                item,
                actor=request.user,
                to_status=serializer.validated_data["to_status"],
                request=request,
            )
        )
        return Response(detail(item, request.user))


class TravellerListView(APIView):
    def get(self, request, itinerary_id):
        item = scoped_itinerary(request.user, itinerary_id)
        require(request.user, item.organization)
        return Response(
            TravellerSerializer(
                item.travellers.select_related("artist", "membership__user"), many=True
            ).data
        )

    def post(self, request, itinerary_id):
        item = scoped_itinerary(request.user, itinerary_id)
        serializer = TravellerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = validation(
            lambda: create_child(
                ItineraryTraveller,
                item,
                actor=request.user,
                data=serializer.validated_data,
                action="travel.traveller_added",
                description="Itinerary traveller added.",
                request=request,
            )
        )
        return Response(TravellerSerializer(row).data, status=201)


class TravellerDetailView(APIView):
    def get_row(self, user, pk):
        return get_object_or_404(
            ItineraryTraveller.objects.select_related(
                "itinerary__organization", "artist", "membership__user"
            ).filter(itinerary__in=itineraries_for_user(user)),
            pk=pk,
        )

    def patch(self, request, traveller_id):
        row = self.get_row(request.user, traveller_id)
        serializer = TravellerSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        row = validation(
            lambda: update_child(
                row,
                actor=request.user,
                data=serializer.validated_data,
                action="travel.traveller_updated",
                description="Itinerary traveller updated.",
                request=request,
            )
        )
        return Response(TravellerSerializer(row).data)

    def delete(self, request, traveller_id):
        row = self.get_row(request.user, traveller_id)
        row.is_active = False
        validation(
            lambda: update_child(
                row,
                actor=request.user,
                data={"is_active": False},
                action="travel.traveller_removed",
                description="Itinerary traveller deactivated.",
                request=request,
            )
        )
        return Response(status=204)


class SegmentListView(APIView):
    def post(self, request, itinerary_id):
        item = scoped_itinerary(request.user, itinerary_id)
        serializer = SegmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = validation(
            lambda: create_child(
                TravelSegment,
                item,
                actor=request.user,
                data=serializer.validated_data,
                action="travel.segment_added",
                description="Travel segment added.",
                request=request,
            )
        )
        return Response(SegmentSerializer(row).data, status=201)


class SegmentDetailView(APIView):
    def get_row(self, user, pk):
        return get_object_or_404(
            TravelSegment.objects.select_related("itinerary__organization").filter(
                itinerary__in=itineraries_for_user(user)
            ),
            pk=pk,
        )

    def patch(self, request, segment_id):
        row = self.get_row(request.user, segment_id)
        serializer = SegmentSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        row = validation(
            lambda: update_child(
                row,
                actor=request.user,
                data=serializer.validated_data,
                action="travel.segment_updated",
                description="Travel segment updated.",
                request=request,
            )
        )
        return Response(SegmentSerializer(row).data)

    def delete(self, request, segment_id):
        row = self.get_row(request.user, segment_id)
        validation(
            lambda: remove_child(
                row,
                actor=request.user,
                action="travel.segment_removed",
                description="Travel segment removed.",
                request=request,
            )
        )
        return Response(status=204)


class SegmentStatusView(APIView):
    def post(self, request, segment_id):
        row = SegmentDetailView().get_row(request.user, segment_id)
        serializer = StatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = validation(
            lambda: transition_child(
                row,
                actor=request.user,
                to_status=serializer.validated_data["to_status"],
                transitions=SEGMENT_TRANSITIONS,
                action="travel.segment_status_changed",
                request=request,
            )
        )
        return Response(SegmentSerializer(row).data)


class SegmentReorderView(APIView):
    def post(self, request, segment_id):
        row = SegmentDetailView().get_row(request.user, segment_id)
        serializer = ReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = reorder_segment(
            row,
            actor=request.user,
            direction=serializer.validated_data["direction"],
            request=request,
        )
        return Response(SegmentSerializer(row).data)


class SegmentTravellerView(APIView):
    def post(self, request, segment_id):
        segment = SegmentDetailView().get_row(request.user, segment_id)
        require(request.user, segment.itinerary.organization, "travel.manage")
        serializer = SegmentTravellerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = TravelSegmentTraveller(segment=segment, **serializer.validated_data)
        validation(row.save)
        record_event(
            actor=request.user,
            organization=segment.itinerary.organization,
            action="travel.segment_updated",
            resource=segment,
            description="Travel segment traveller assignment updated.",
            request=request,
        )
        return Response(SegmentTravellerSerializer(row).data, status=201)

    def delete(self, request, segment_id, assignment_id):
        segment = SegmentDetailView().get_row(request.user, segment_id)
        require(request.user, segment.itinerary.organization, "travel.manage")
        row = get_object_or_404(TravelSegmentTraveller, pk=assignment_id, segment=segment)
        row.delete()
        return Response(status=204)


class StayListView(APIView):
    def post(self, request, itinerary_id):
        item = scoped_itinerary(request.user, itinerary_id)
        serializer = StaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = validation(
            lambda: create_child(
                AccommodationStay,
                item,
                actor=request.user,
                data=serializer.validated_data,
                action="travel.accommodation_added",
                description="Accommodation stay added.",
                request=request,
            )
        )
        return Response(StaySerializer(row).data, status=201)


class StayDetailView(APIView):
    def get_row(self, user, pk):
        return get_object_or_404(
            AccommodationStay.objects.select_related("itinerary__organization").filter(
                itinerary__in=itineraries_for_user(user)
            ),
            pk=pk,
        )

    def patch(self, request, stay_id):
        row = self.get_row(request.user, stay_id)
        serializer = StaySerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        row = validation(
            lambda: update_child(
                row,
                actor=request.user,
                data=serializer.validated_data,
                action="travel.accommodation_updated",
                description="Accommodation stay updated.",
                request=request,
            )
        )
        return Response(StaySerializer(row).data)

    def delete(self, request, stay_id):
        row = self.get_row(request.user, stay_id)
        validation(
            lambda: remove_child(
                row,
                actor=request.user,
                action="travel.accommodation_removed",
                description="Accommodation stay removed.",
                request=request,
            )
        )
        return Response(status=204)


class StayStatusView(APIView):
    def post(self, request, stay_id):
        row = StayDetailView().get_row(request.user, stay_id)
        serializer = StatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = validation(
            lambda: transition_child(
                row,
                actor=request.user,
                to_status=serializer.validated_data["to_status"],
                transitions=STAY_TRANSITIONS,
                action="travel.accommodation_status_changed",
                request=request,
            )
        )
        return Response(StaySerializer(row).data)


class RoomView(APIView):
    def post(self, request, stay_id):
        stay = StayDetailView().get_row(request.user, stay_id)
        require(request.user, stay.itinerary.organization, "travel.manage")
        serializer = RoomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = AccommodationRoomAssignment(stay=stay, **serializer.validated_data)
        validation(row.save)
        record_event(
            actor=request.user,
            organization=stay.itinerary.organization,
            action="travel.room_assigned",
            resource=row,
            description="Accommodation room assigned.",
            request=request,
        )
        return Response(RoomSerializer(row).data, status=201)

    def patch(self, request, stay_id, room_id):
        stay = StayDetailView().get_row(request.user, stay_id)
        require(request.user, stay.itinerary.organization, "travel.manage")
        row = get_object_or_404(AccommodationRoomAssignment, pk=room_id, stay=stay)
        serializer = RoomSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for key, value in serializer.validated_data.items():
            setattr(row, key, value)
        validation(row.save)
        record_event(
            actor=request.user,
            organization=stay.itinerary.organization,
            action="travel.room_updated",
            resource=row,
            description="Accommodation room assignment updated.",
            request=request,
        )
        return Response(RoomSerializer(row).data)

    def delete(self, request, stay_id, room_id):
        stay = StayDetailView().get_row(request.user, stay_id)
        require(request.user, stay.itinerary.organization, "travel.manage")
        row = get_object_or_404(AccommodationRoomAssignment, pk=room_id, stay=stay)
        row.delete()
        record_event(
            actor=request.user,
            organization=stay.itinerary.organization,
            action="travel.room_removed",
            resource=row,
            description="Accommodation room assignment removed.",
            request=request,
        )
        return Response(status=204)


class PlatformItineraryListView(APIView):
    permission_classes = [PlatformSuperuser]

    def get(self, request):
        rows = itineraries_for_user(request.user).annotate(
            traveller_count=Count("travellers", distinct=True)
        )
        return Response(
            {"count": rows.count(), "results": ItineraryListSerializer(rows[:100], many=True).data}
        )


class PlatformItineraryDetailView(APIView):
    permission_classes = [PlatformSuperuser]

    def get(self, request, itinerary_id):
        return Response(
            detail(
                get_object_or_404(itineraries_for_user(request.user), pk=itinerary_id),
                request.user,
            )
        )


class ArtistTravelView(APIView):
    def get(self, request):
        return Response(
            ArtistItinerarySerializer(artist_itineraries_for_user(request.user), many=True).data
        )


class DeveloperTravelView(APIView):
    permission_classes = []

    def get(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise PermissionDenied("Invalid API credentials.")
        key = authenticate_api_key(header[7:], required_scope="travel.read")
        rows = itinerary_queryset().filter(organization=key.client.organization)
        return Response(DeveloperItinerarySerializer(rows, many=True).data)
