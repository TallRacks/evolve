import math
import uuid
from datetime import date

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
from reporting.services import REPORT_COLUMNS, REPORT_FILTERS, REPORTS, report_data, safe_csv

from .serializers import SavedReportViewSerializer

FILTER_KEYS = {
    "status",
    "priority",
    "artist",
    "promoter",
    "venue",
    "assignee",
    "date_from",
    "date_to",
}
UUID_FILTERS = {"artist", "promoter", "venue", "assignee"}
MAX_PAGE_SIZE = 100


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


def validated_filters(params, report_key):
    supplied = {key for key in FILTER_KEYS if params.get(key)}
    unsupported = supplied - REPORT_FILTERS[report_key]
    if unsupported:
        raise ValidationError(
            {key: "Filter is not supported for this report." for key in unsupported}
        )
    filters = {key: params.get(key) for key in supplied}
    errors = {}
    for key in UUID_FILTERS & filters.keys():
        try:
            uuid.UUID(filters[key])
        except (ValueError, TypeError, AttributeError):
            errors[key] = "Use a valid UUID."
    for key in {"date_from", "date_to"} & filters.keys():
        try:
            date.fromisoformat(filters[key])
        except (ValueError, TypeError):
            errors[key] = "Use an ISO date in YYYY-MM-DD format."
    if not errors and filters.get("date_from") and filters.get("date_to"):
        if filters["date_from"] > filters["date_to"]:
            errors["date_to"] = "End date must not precede start date."
    if errors:
        raise ValidationError(errors)
    return filters


def pagination(params, total):
    try:
        page = max(1, int(params.get("page", 1)))
        page_size = min(MAX_PAGE_SIZE, max(1, int(params.get("page_size", 25))))
    except (TypeError, ValueError):
        raise ValidationError({"page": "Page and page_size must be integers."}) from None
    pages = max(1, math.ceil(total / page_size))
    if page > pages and total:
        raise ValidationError({"page": "Page exceeds the available result set."})
    return page, page_size, pages


class ReportingAPIView(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            exc = ValidationError(getattr(exc, "message_dict", exc.messages))
        return super().handle_exception(exc)


class ReportView(ReportingAPIView):
    def get(self, request, report_key=None):
        organization = scoped(request)
        report_key = report_key or request.query_params.get("report_key", "bookings")
        authorize(request, organization, report_key)
        filters = validated_filters(request.query_params, report_key)
        report = report_data(organization, report_key, filters)
        sort = request.query_params.get("sort", "")
        sort_key = sort.removeprefix("-")
        if sort_key and sort_key not in REPORT_COLUMNS[report_key]:
            raise ValidationError({"sort": "Unsupported sort field."})
        if sort_key:
            report["rows"].sort(
                key=lambda row: str(row.get(sort_key, "")).lower(), reverse=sort.startswith("-")
            )
        total = len(report["rows"])
        page, page_size, pages = pagination(request.query_params, total)
        start = (page - 1) * page_size
        report["rows"] = report["rows"][start : start + page_size]
        report["pagination"] = {
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "total": total,
        }
        report["filters"] = filters
        return Response(report)


class ReportExportView(ReportingAPIView):
    def get(self, request, report_key=None):
        organization = scoped(request)
        report_key = report_key or request.query_params.get("report_key", "bookings")
        authorize(request, organization, report_key)
        filters = validated_filters(request.query_params, report_key)
        report = report_data(organization, report_key, filters)
        record_event(
            actor=request.user,
            organization=organization,
            action="report.exported",
            resource=organization,
            description=(
                f"Exported {report_key} report with {len(report['rows'])} rows; "
                f"filter keys: {', '.join(sorted(filters)) or 'none'}."
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

    @transaction.atomic
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
