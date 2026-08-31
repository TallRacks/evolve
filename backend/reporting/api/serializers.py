import uuid
from datetime import date

from rest_framework import serializers

from reporting.models import SavedReportView
from reporting.services import REPORT_COLUMNS, REPORT_FILTERS, REPORTS

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


class SavedReportViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedReportView
        fields = (
            "id",
            "organization",
            "report_key",
            "name",
            "filters",
            "sort",
            "is_default",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization", "created_at", "updated_at")

    def validate_report_key(self, value):
        if value not in REPORTS:
            raise serializers.ValidationError("Unknown report key.")
        return value

    def validate_filters(self, value):
        if not isinstance(value, dict) or any(key not in FILTER_KEYS for key in value):
            raise serializers.ValidationError("Report filters contain unsupported keys.")
        for key, item in value.items():
            if not isinstance(item, str) or len(item) > 120:
                raise serializers.ValidationError({key: "Use a short text filter value."})
            if key in UUID_FILTERS and item:
                try:
                    uuid.UUID(item)
                except (ValueError, TypeError, AttributeError):
                    raise serializers.ValidationError({key: "Use a valid UUID."}) from None
            if key in {"date_from", "date_to"} and item:
                try:
                    date.fromisoformat(item)
                except (ValueError, TypeError):
                    raise serializers.ValidationError(
                        {key: "Use an ISO date in YYYY-MM-DD format."}
                    ) from None
        if value.get("date_from") and value.get("date_to"):
            if value["date_from"] > value["date_to"]:
                raise serializers.ValidationError({"date_to": "End date precedes start date."})
        return value

    def validate_sort(self, value):
        if not value:
            return value
        allowed = {column for columns in REPORT_COLUMNS.values() for column in columns}
        if value.removeprefix("-") not in allowed:
            raise serializers.ValidationError("Unsupported sort field.")
        return value

    def validate(self, attrs):
        report_key = attrs.get("report_key", getattr(self.instance, "report_key", None))
        sort = attrs.get("sort", getattr(self.instance, "sort", ""))
        filters = attrs.get("filters", getattr(self.instance, "filters", {}))
        if report_key and set(filters) - REPORT_FILTERS[report_key]:
            raise serializers.ValidationError({"filters": "Filters are not valid for this report."})
        if report_key and sort and sort.removeprefix("-") not in REPORT_COLUMNS[report_key]:
            raise serializers.ValidationError({"sort": "Sort is not valid for this report."})
        return attrs
