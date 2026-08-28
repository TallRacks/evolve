from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import SavedReportView


@admin.register(SavedReportView)
class SavedReportViewAdmin(ModelAdmin):
    list_display = ("name", "report_key", "organization", "user", "is_default", "updated_at")
    readonly_fields = ("id", "created_at", "updated_at")
