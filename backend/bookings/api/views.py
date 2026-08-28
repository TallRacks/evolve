from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking, BookingContactAssignment, BookingTeamAssignment
from bookings.selectors import booking_activity, bookings_for_user
from bookings.services import (
    allowed_transitions,
    assign_contact,
    assign_team_member,
    create_booking,
    create_booking_with_setup,
    require_booking_permission,
    setup_booking_operations,
    transition_booking,
    update_booking,
    update_contact_assignment,
    update_team_assignment,
)
from contacts.models import Contact
from organizations.api.permissions import PlatformSuperuser
from organizations.models import Membership, Organization
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from white_label.services import authenticate_api_key

from .serializers import (
    BookingContactAssignmentSerializer,
    BookingContactCreateSerializer,
    BookingCreateSerializer,
    BookingDetailSerializer,
    BookingListSerializer,
    BookingSetupSerializer,
    BookingStatusHistorySerializer,
    BookingTeamAssignmentSerializer,
    BookingTeamCreateSerializer,
    BookingWriteSerializer,
    DeveloperBookingSerializer,
    StatusTransitionSerializer,
)


def booking_queryset():
    return Booking.objects.select_related(
        "organization", "artist", "promoter", "venue", "created_by"
    )


def scoped_organization(user, organization_id):
    return get_object_or_404(
        Organization.objects.filter(pk__in=organizations_for_user(user).values("pk")),
        pk=organization_id,
    )


def scoped_booking(user, booking_id):
    return get_object_or_404(
        booking_queryset().filter(pk__in=bookings_for_user(user).values("pk")), pk=booking_id
    )


def validation_call(call):
    try:
        return call()
    except DjangoValidationError as error:
        detail = error.message_dict if hasattr(error, "message_dict") else error.messages
        raise ValidationError(detail) from error


def filtered(queryset, request):
    search = request.query_params.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(reference__icontains=search)
            | Q(artist__stage_name__icontains=search)
            | Q(promoter_name_snapshot__icontains=search)
            | Q(venue_name_snapshot__icontains=search)
        )
    mappings = {
        "artist": "artist_id",
        "promoter": "promoter_id",
        "venue": "venue_id",
        "status": "status",
        "priority": "priority",
        "organization_id": "organization_id",
    }
    for parameter, field in mappings.items():
        if request.query_params.get(parameter):
            queryset = queryset.filter(**{field: request.query_params[parameter]})
    if request.query_params.get("date_from"):
        queryset = queryset.filter(event_date__gte=request.query_params["date_from"])
    if request.query_params.get("date_to"):
        queryset = queryset.filter(event_date__lte=request.query_params["date_to"])
    if request.query_params.get("assigned_membership"):
        queryset = queryset.filter(
            team_assignments__membership_id=request.query_params["assigned_membership"],
            team_assignments__is_active=True,
        )
    return queryset.distinct()


def activity_data(booking):
    return [
        {
            "id": event.id,
            "action": event.action,
            "description": event.description,
            "actor": event.actor.email if event.actor else None,
            "created_at": event.created_at,
        }
        for event in booking_activity(booking)
    ]


def detail_data(user, booking):
    include_commercial = user_has_organization_permission(
        user, booking.organization, "booking.commercial.view"
    )
    transitions = []
    if user_has_organization_permission(user, booking.organization, "booking.status.manage"):
        transitions = allowed_transitions(booking)
    return BookingDetailSerializer(
        booking,
        context={
            "include_commercial": include_commercial,
            "allowed_transitions": transitions,
            "activity": activity_data(booking),
        },
    ).data


class BookingListView(APIView):
    def get(self, request):
        organization = scoped_organization(
            request.user, request.query_params.get("organization_id")
        )
        require_booking_permission(request.user, organization, "booking.view")
        return Response(
            BookingListSerializer(
                filtered(booking_queryset().filter(organization=organization), request),
                many=True,
            ).data
        )

    def post(self, request):
        organization = scoped_organization(request.user, request.data.get("organization_id"))
        require_booking_permission(request.user, organization, "booking.manage")
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        setup = {
            "create_production": values.pop("prepare_production"),
            "create_call_sheet": values.pop("prepare_call_sheet"),
            "create_travel": values.pop("prepare_travel"),
        }
        membership_id = values.pop("initial_membership_id", None)
        contact_id = values.pop("initial_contact_id", None)
        initial_membership = None
        initial_contact = None
        if membership_id:
            initial_membership = get_object_or_404(
                Membership.objects.select_related("user"),
                pk=membership_id,
                organization=organization,
                is_active=True,
                user__is_active=True,
            )
        if contact_id:
            initial_contact = get_object_or_404(
                Contact, pk=contact_id, organization=organization, is_active=True
            )
        booking, operations = validation_call(
            lambda: create_booking_with_setup(
                actor=request.user,
                organization=organization,
                data=values,
                initial_membership=initial_membership,
                initial_contact=initial_contact,
                **setup,
                request=request,
            )
        )
        data = detail_data(request.user, booking)
        data["operations"] = {
            key: str(value.pk) if value else None for key, value in operations.items()
        }
        return Response(data, status=status.HTTP_201_CREATED)


class BookingSetupView(APIView):
    def post(self, request, booking_id):
        booking = scoped_booking(request.user, booking_id)
        serializer = BookingSetupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        operations = validation_call(
            lambda: setup_booking_operations(
                actor=request.user,
                booking=booking,
                **serializer.validated_data,
                request=request,
            )
        )
        return Response(
            {key: str(value.pk) if value else None for key, value in operations.items()}
        )


class BookingDetailView(APIView):
    def get(self, request, booking_id):
        booking = scoped_booking(request.user, booking_id)
        require_booking_permission(request.user, booking.organization, "booking.view")
        return Response(detail_data(request.user, booking))

    def patch(self, request, booking_id):
        booking = scoped_booking(request.user, booking_id)
        require_booking_permission(request.user, booking.organization, "booking.manage")
        if "status" in request.data:
            raise ValidationError({"status": "Use the status transition endpoint."})
        serializer = BookingWriteSerializer(booking, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        booking = validation_call(
            lambda: update_booking(
                actor=request.user,
                booking=booking,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(detail_data(request.user, booking))


class BookingStatusView(APIView):
    def post(self, request, booking_id):
        booking = scoped_booking(request.user, booking_id)
        require_booking_permission(request.user, booking.organization, "booking.status.manage")
        serializer = StatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = validation_call(
            lambda: transition_booking(
                actor=request.user,
                booking=booking,
                to_status=serializer.validated_data["to_status"],
                reason=serializer.validated_data.get("reason", ""),
                request=request,
            )
        )
        return Response(detail_data(request.user, booking))


class BookingStatusHistoryView(APIView):
    def get(self, request, booking_id):
        booking = scoped_booking(request.user, booking_id)
        require_booking_permission(request.user, booking.organization, "booking.view")
        return Response(
            BookingStatusHistorySerializer(
                booking.status_history.select_related("changed_by"), many=True
            ).data
        )


class BookingTeamView(APIView):
    def get(self, request, booking_id):
        booking = scoped_booking(request.user, booking_id)
        require_booking_permission(request.user, booking.organization, "booking.view")
        return Response(
            BookingTeamAssignmentSerializer(
                booking.team_assignments.select_related("membership__user"), many=True
            ).data
        )

    def post(self, request, booking_id):
        booking = scoped_booking(request.user, booking_id)
        require_booking_permission(request.user, booking.organization, "booking.team.manage")
        serializer = BookingTeamCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = get_object_or_404(
            Membership.objects.select_related("organization", "user"),
            pk=serializer.validated_data.pop("membership_id"),
            organization=booking.organization,
        )
        assignment = validation_call(
            lambda: assign_team_member(
                actor=request.user,
                booking=booking,
                membership=membership,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(
            BookingTeamAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )


class BookingTeamDetailView(APIView):
    def patch(self, request, booking_id, assignment_id):
        booking = scoped_booking(request.user, booking_id)
        require_booking_permission(request.user, booking.organization, "booking.team.manage")
        assignment = get_object_or_404(BookingTeamAssignment, pk=assignment_id, booking=booking)
        serializer = BookingTeamAssignmentSerializer(assignment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        assignment = validation_call(
            lambda: update_team_assignment(
                actor=request.user,
                assignment=assignment,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(BookingTeamAssignmentSerializer(assignment).data)


class BookingContactsView(APIView):
    def get(self, request, booking_id):
        booking = scoped_booking(request.user, booking_id)
        require_booking_permission(request.user, booking.organization, "booking.view")
        return Response(
            BookingContactAssignmentSerializer(
                booking.contact_assignments.select_related("contact"), many=True
            ).data
        )

    def post(self, request, booking_id):
        booking = scoped_booking(request.user, booking_id)
        require_booking_permission(request.user, booking.organization, "booking.manage")
        serializer = BookingContactCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact = get_object_or_404(
            Contact,
            pk=serializer.validated_data.pop("contact_id"),
            organization=booking.organization,
        )
        assignment = validation_call(
            lambda: assign_contact(
                actor=request.user,
                booking=booking,
                contact=contact,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(
            BookingContactAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )


class BookingContactDetailView(APIView):
    def patch(self, request, booking_id, assignment_id):
        booking = scoped_booking(request.user, booking_id)
        require_booking_permission(request.user, booking.organization, "booking.manage")
        assignment = get_object_or_404(BookingContactAssignment, pk=assignment_id, booking=booking)
        serializer = BookingContactAssignmentSerializer(assignment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        assignment = validation_call(
            lambda: update_contact_assignment(
                actor=request.user,
                assignment=assignment,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(BookingContactAssignmentSerializer(assignment).data)


class PlatformBookingListView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        return Response(
            BookingListSerializer(filtered(booking_queryset(), request), many=True).data
        )

    def post(self, request):
        organization = get_object_or_404(Organization, pk=request.data.get("organization_id"))
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = validation_call(
            lambda: create_booking(
                actor=request.user,
                organization=organization,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(detail_data(request.user, booking), status=status.HTTP_201_CREATED)


class PlatformBookingDetailView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request, booking_id):
        return Response(
            detail_data(request.user, get_object_or_404(booking_queryset(), pk=booking_id))
        )

    def patch(self, request, booking_id):
        if "status" in request.data:
            raise ValidationError({"status": "Use the status transition endpoint."})
        booking = get_object_or_404(booking_queryset(), pk=booking_id)
        serializer = BookingWriteSerializer(booking, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        booking = validation_call(
            lambda: update_booking(
                actor=request.user, booking=booking, data=serializer.validated_data, request=request
            )
        )
        return Response(detail_data(request.user, booking))


class DeveloperBookingListView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise PermissionDenied("Invalid API credentials.")
        key = authenticate_api_key(header[7:], required_scope="booking.read")
        bookings = filtered(
            booking_queryset().filter(organization=key.client.organization), request
        )
        return Response(DeveloperBookingSerializer(bookings, many=True).data)
