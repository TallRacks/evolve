from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import record_event
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from reporting.models import SavedReportView
from reporting.services import REPORTS, report_data, safe_csv

from .serializers import SavedReportViewSerializer


def scoped(request):
    organization_id = request.query_params.get("organization_id") or request.data.get(
        "organization_id"
    )
    if not organization_id:
        raise ValidationError({"organization_id": "This field is required."})
    return get_object_or_404(organizations_for_user(request.user), pk=organization_id)


def authorize(request, organization, report_key):
    if report_key not in REPORTS:
        raise ValidationError({"report_key": "Unknown report."})
    for permission in ("reporting.view", REPORTS[report_key][1]):
        if not user_has_organization_permission(request.user, organization, permission):
            raise PermissionDenied("You do not have permission for this report.")


class ReportingAPIView(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            exc = ValidationError(getattr(exc, "message_dict", exc.messages))
        return super().handle_exception(exc)


class ReportView(ReportingAPIView):
    def get(self, request):
        organization = scoped(request)
        report_key = request.query_params.get("report_key", "bookings")
        authorize(request, organization, report_key)
        filters = {
            key: request.query_params.get(key)
            for key in (
                "status",
                "priority",
                "artist",
                "promoter",
                "venue",
                "assignee",
                "date_from",
                "date_to",
            )
            if request.query_params.get(key)
        }
        return Response(report_data(organization, report_key, filters))


class ReportExportView(ReportingAPIView):
    def get(self, request):
        organization = scoped(request)
        report_key = request.query_params.get("report_key", "bookings")
        authorize(request, organization, report_key)
        filters = {
            key: request.query_params.get(key)
            for key in (
                "status",
                "priority",
                "artist",
                "promoter",
                "venue",
                "assignee",
                "date_from",
                "date_to",
            )
            if request.query_params.get(key)
        }
        report = report_data(organization, report_key, filters)
        filter_names = ", ".join(sorted(filters)) or "none"
        record_event(
            actor=request.user,
            organization=organization,
            action="report.exported",
            resource=organization,
            description=(
                f"Exported {report_key} report with {len(report['rows'])} rows; "
                f"filters: {filter_names}."
            ),
            request=request,
        )
        response = HttpResponse(safe_csv(report), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="evolve-{report_key}.csv"'
        return response


class SavedViewCollection(ReportingAPIView):
    def get(self, request):
        organization = scoped(request)
        if not user_has_organization_permission(request.user, organization, "reporting.view"):
            raise PermissionDenied()
        rows = SavedReportView.objects.filter(organization=organization, user=request.user)
        return Response(SavedReportViewSerializer(rows, many=True).data)

    @transaction.atomic
    def post(self, request):
        organization = scoped(request)
        report_key = request.data.get("report_key")
        authorize(request, organization, report_key)
        serializer = SavedReportViewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("is_default"):
            SavedReportView.objects.filter(
                organization=organization, user=request.user, report_key=report_key, is_default=True
            ).update(is_default=False)
        item = serializer.save(organization=organization, user=request.user)
        record_event(
            actor=request.user,
            organization=organization,
            action="report.saved_view_created",
            resource=item,
            description=f"Created saved report view {item.name}.",
            request=request,
        )
        return Response(SavedReportViewSerializer(item).data, status=status.HTTP_201_CREATED)


class SavedViewDetail(ReportingAPIView):
    def item(self, request, pk):
        return get_object_or_404(
            SavedReportView,
            pk=pk,
            user=request.user,
            organization__in=organizations_for_user(request.user),
        )

    @transaction.atomic
    def patch(self, request, pk):
        item = self.item(request, pk)
        next_report_key = request.data.get("report_key", item.report_key)
        authorize(request, item.organization, next_report_key)
        serializer = SavedReportViewSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("is_default"):
            SavedReportView.objects.filter(
                organization=item.organization,
                user=request.user,
                report_key=next_report_key,
                is_default=True,
            ).exclude(pk=item.pk).update(is_default=False)
        item = serializer.save()
        record_event(
            actor=request.user,
            organization=item.organization,
            action="report.saved_view_updated",
            resource=item,
            description=f"Updated saved report view {item.name}.",
            request=request,
        )
        return Response(SavedReportViewSerializer(item).data)

    def delete(self, request, pk):
        item = self.item(request, pk)
        authorize(request, item.organization, item.report_key)
        organization = item.organization
        name = item.name
        record_event(
            actor=request.user,
            organization=organization,
            action="report.saved_view_deleted",
            resource=item,
            description=f"Deleted saved report view {name}.",
            request=request,
        )
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
