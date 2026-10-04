from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from trackers.models import Tracker
from trackers.services import reconcile_schema, request_sync, tracker_fields
from .serializers import TrackerSerializer, TrackerSyncEventSerializer
def organization_for_request(request):
    return get_object_or_404(organizations_for_user(request.user), pk=request.query_params.get("organization_id") or request.data.get("organization_id"))
class TrackerView(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError): exc = ValidationError(getattr(exc, "message_dict", exc.messages))
        return super().handle_exception(exc)
    def get_object(self, request, pk):
        return get_object_or_404(Tracker, pk=pk, organization=organization_for_request(request))

    def get(self, request):
        organization = organization_for_request(request)
        if not user_has_organization_permission(request.user, organization, "calendar.view"):
            raise ValidationError("Calendar view permission is required for trackers.")
        return Response(TrackerSerializer(Tracker.objects.filter(organization=organization), many=True).data)
    def post(self, request):
        organization = organization_for_request(request)
        if not user_has_organization_permission(request.user, organization, "calendar.manage"):
            raise ValidationError("Calendar management permission is required to create trackers.")
        serializer = TrackerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        connector = serializer.validated_data.get("google_connector")
        if connector and connector.organization_id not in (None, organization.id):
            raise ValidationError({"google_connector": "The selected Google connector is not available to this organization."})
        try:
            item = serializer.save(organization=organization, created_by=request.user)
        except IntegrityError as exc:
            if "one_tracker_kind_per_organization" in str(exc):
                raise ValidationError({"kind": "This organization already has a tracker for that data type. Edit the existing tracker instead."}) from exc
            raise
        return Response(TrackerSerializer(item).data, status=status.HTTP_201_CREATED)
class TrackerDetailView(TrackerView):
    def get_object(self, request, pk):
        return get_object_or_404(Tracker, pk=pk, organization=organization_for_request(request))
    def get(self, request, pk):
        item = self.get_object(request, pk)
        if not user_has_organization_permission(request.user, item.organization, "calendar.view"):
            raise ValidationError("Calendar view permission is required for trackers.")
        return Response(TrackerSerializer(item).data)
    def patch(self, request, pk):
        item = self.get_object(request, pk)
        if not user_has_organization_permission(request.user, item.organization, "calendar.manage"):
            raise ValidationError("Calendar management permission is required to edit trackers.")
        serializer = TrackerSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(TrackerSerializer(serializer.save()).data)
class TrackerSyncView(TrackerView):
    def post(self, request, pk):
        item=self.get_object(request, pk); direction=request.data.get("direction", "import")
        if direction not in {"import", "export"}: raise ValidationError({"direction": "Use import or export."})
        return Response(TrackerSyncEventSerializer(request_sync(actor=request.user, tracker=item, direction=direction, request=request)).data, status=status.HTTP_202_ACCEPTED)
class TrackerHistoryView(TrackerView):
    def get(self, request, pk): return Response(TrackerSyncEventSerializer(self.get_object(request, pk).sync_events.all()[:50], many=True).data)


class TrackerSchemaView(TrackerView):
    def get(self, request, pk):
        item = self.get_object(request, pk)
        return Response({"tracker_id": str(item.id), "kind": item.kind, "fields": tracker_fields(item), "state": item.schema_state})

    def post(self, request, pk):
        item = self.get_object(request, pk)
        columns = request.data.get("columns")
        if columns is None:
            from trackers.services import _sheet_headers
            columns = _sheet_headers(item)
        state = reconcile_schema(tracker=item, columns=columns, apply_headers=bool(request.data.get("apply_headers")), actor=request.user, request=request)
        return Response(state)
