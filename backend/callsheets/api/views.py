from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.selectors import bookings_for_user
from callsheets.models import (
    CallSheet,
    CallSheetContactEntry,
    CallSheetTeamEntry,
    CallSheetVersion,
)
from callsheets.selectors import call_sheets_for_user, versions_for_user
from callsheets.services import (
    cancel_version,
    create_call_sheet,
    create_call_sheet_version,
    create_child,
    import_production_from_advance,
    import_travel_from_itinerary,
    mark_ready,
    publish_call_sheet_version,
    refresh_all_sources,
    refresh_from_booking,
    remove_child,
    require_callsheet_permission,
    update_child,
    update_version,
)
from contacts.models import Contact
from organizations.api.permissions import PlatformSuperuser
from organizations.models import Membership
from white_label.services import authenticate_api_key

from .serializers import (
    CallSheetSerializer,
    DeveloperCallSheetSerializer,
    VersionCreateSerializer,
    VersionSerializer,
    VersionWriteSerializer,
)


def validated(call):
    try:
        return call()
    except DjangoValidationError as error:
        detail = error.message_dict if hasattr(error, "message_dict") else error.messages
        raise ValidationError(detail) from error


def scoped_booking(user, booking_id):
    return get_object_or_404(
        bookings_for_user(user).select_related("organization", "artist", "venue", "promoter"),
        pk=booking_id,
    )


def scoped_call_sheet(user, call_sheet_id):
    return get_object_or_404(call_sheets_for_user(user), pk=call_sheet_id)


def scoped_version(user, version_id):
    return get_object_or_404(versions_for_user(user), pk=version_id)


class BookingCallSheetView(APIView):
    def get(self, request, booking_id):
        booking = scoped_booking(request.user, booking_id)
        require_callsheet_permission(request.user, booking.organization, "callsheet.view")
        call_sheet = get_object_or_404(call_sheets_for_user(request.user), booking=booking)
        return Response(CallSheetSerializer(call_sheet).data)

    def post(self, request, booking_id):
        booking = scoped_booking(request.user, booking_id)
        require_callsheet_permission(request.user, booking.organization, "callsheet.manage")
        existed = CallSheet.objects.filter(booking=booking).exists()
        call_sheet, _ = validated(
            lambda: create_call_sheet(actor=request.user, booking=booking, request=request)
        )
        response_status = status.HTTP_200_OK if existed else status.HTTP_201_CREATED
        return Response(CallSheetSerializer(call_sheet).data, status=response_status)


class CallSheetDetailView(APIView):
    def get(self, request, call_sheet_id):
        call_sheet = scoped_call_sheet(request.user, call_sheet_id)
        require_callsheet_permission(request.user, call_sheet.organization, "callsheet.view")
        return Response(CallSheetSerializer(call_sheet).data)


class VersionListView(APIView):
    def get(self, request, call_sheet_id):
        call_sheet = scoped_call_sheet(request.user, call_sheet_id)
        require_callsheet_permission(request.user, call_sheet.organization, "callsheet.view")
        return Response(VersionSerializer(call_sheet.versions.all(), many=True).data)

    def post(self, request, call_sheet_id):
        call_sheet = scoped_call_sheet(request.user, call_sheet_id)
        require_callsheet_permission(request.user, call_sheet.organization, "callsheet.manage")
        serializer = VersionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source = None
        if serializer.validated_data.get("source_version_id"):
            source = get_object_or_404(
                call_sheet.versions, pk=serializer.validated_data["source_version_id"]
            )
        version = validated(
            lambda: create_call_sheet_version(
                actor=request.user, call_sheet=call_sheet, source_version=source, request=request
            )
        )
        return Response(VersionSerializer(version).data, status=status.HTTP_201_CREATED)


class VersionDetailView(APIView):
    def get(self, request, version_id):
        version = scoped_version(request.user, version_id)
        require_callsheet_permission(
            request.user, version.call_sheet.organization, "callsheet.view"
        )
        return Response(VersionSerializer(version).data)

    def patch(self, request, version_id):
        version = scoped_version(request.user, version_id)
        require_callsheet_permission(
            request.user, version.call_sheet.organization, "callsheet.manage"
        )
        if "status" in request.data:
            raise ValidationError({"status": "Use a lifecycle endpoint."})
        serializer = VersionWriteSerializer(version, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        version = validated(
            lambda: update_version(
                actor=request.user, version=version, data=serializer.validated_data, request=request
            )
        )
        return Response(VersionSerializer(version).data)


class LifecycleView(APIView):
    operation = None

    def post(self, request, version_id):
        version = scoped_version(request.user, version_id)
        operations = {
            "ready": mark_ready,
            "publish": publish_call_sheet_version,
            "cancel": cancel_version,
            "refresh": refresh_from_booking,
            "import-travel": import_travel_from_itinerary,
            "import-production": import_production_from_advance,
            "refresh-all": refresh_all_sources,
        }
        version = validated(
            lambda: operations[self.operation](actor=request.user, version=version, request=request)
        )
        return Response(VersionSerializer(version).data)


class ChildListView(APIView):
    model = None
    serializer_class = None
    relation = None
    audit_action = None
    create_action = None

    def get(self, request, version_id):
        version = scoped_version(request.user, version_id)
        require_callsheet_permission(
            request.user, version.call_sheet.organization, "callsheet.view"
        )
        return Response(
            self.serializer_class(getattr(version, self.relation).all(), many=True).data
        )

    def post(self, request, version_id):
        version = scoped_version(request.user, version_id)
        require_callsheet_permission(
            request.user, version.call_sheet.organization, "callsheet.manage"
        )
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if self.model is CallSheetTeamEntry:
            membership_id = data.pop("membership_id", None)
            assignment_id = data.pop("booking_team_assignment_id", None)
            data["membership"] = (
                get_object_or_404(
                    Membership, pk=membership_id, organization=version.call_sheet.organization
                )
                if membership_id
                else None
            )
            data["booking_team_assignment_id"] = assignment_id
        if self.model is CallSheetContactEntry:
            contact_id = data.pop("source_contact_id", None)
            data["source_contact"] = (
                get_object_or_404(
                    Contact, pk=contact_id, organization=version.call_sheet.organization
                )
                if contact_id
                else None
            )
        child = validated(
            lambda: create_child(
                actor=request.user,
                version=version,
                model=self.model,
                data=data,
                action=self.create_action or self.audit_action,
                request=request,
            )
        )
        return Response(self.serializer_class(child).data, status=status.HTTP_201_CREATED)


class ChildDetailView(APIView):
    model = None
    serializer_class = None
    audit_action = None
    remove_action = None

    def child(self, request, version_id, child_id):
        version = scoped_version(request.user, version_id)
        return get_object_or_404(self.model, pk=child_id, version=version)

    def patch(self, request, version_id, child_id):
        child = self.child(request, version_id, child_id)
        require_callsheet_permission(
            request.user, child.version.call_sheet.organization, "callsheet.manage"
        )
        serializer = self.serializer_class(child, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if self.model is CallSheetTeamEntry:
            membership_id = data.pop("membership_id", None)
            if "membership_id" in request.data:
                data["membership"] = (
                    get_object_or_404(
                        Membership,
                        pk=membership_id,
                        organization=child.version.call_sheet.organization,
                    )
                    if membership_id
                    else None
                )
        if self.model is CallSheetContactEntry:
            contact_id = data.pop("source_contact_id", None)
            if "source_contact_id" in request.data:
                data["source_contact"] = (
                    get_object_or_404(
                        Contact, pk=contact_id, organization=child.version.call_sheet.organization
                    )
                    if contact_id
                    else None
                )
        child = validated(
            lambda: update_child(
                actor=request.user,
                child=child,
                data=data,
                action=self.audit_action,
                request=request,
            )
        )
        return Response(self.serializer_class(child).data)

    def delete(self, request, version_id, child_id):
        child = self.child(request, version_id, child_id)
        require_callsheet_permission(
            request.user, child.version.call_sheet.organization, "callsheet.manage"
        )
        validated(
            lambda: remove_child(
                actor=request.user, child=child, action=self.remove_action, request=request
            )
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlatformCallSheetListView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        return Response(CallSheetSerializer(call_sheets_for_user(request.user), many=True).data)


class PlatformCallSheetDetailView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request, call_sheet_id):
        return Response(
            CallSheetSerializer(
                get_object_or_404(call_sheets_for_user(request.user), pk=call_sheet_id)
            ).data
        )


class DeveloperCallSheetListView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise PermissionDenied("Invalid API credentials.")
        key = authenticate_api_key(header[7:], required_scope="callsheet.read")
        versions = CallSheetVersion.objects.filter(
            call_sheet__organization=key.client.organization,
            status=CallSheetVersion.Status.PUBLISHED,
        ).select_related("call_sheet__booking")
        return Response(DeveloperCallSheetSerializer(versions, many=True).data)
