from rest_framework import serializers

from reporting.models import SavedReportView
from reporting.services import REPORTS


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
        allowed = {
            "status",
            "priority",
            "artist",
            "promoter",
            "venue",
            "assignee",
            "date_from",
            "date_to",
        }
        if not isinstance(value, dict) or any(key not in allowed for key in value):
            raise serializers.ValidationError("Report filters contain unsupported keys.")
        return value
