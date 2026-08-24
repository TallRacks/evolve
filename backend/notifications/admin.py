from django.contrib import admin
from unfold.admin import ModelAdmin

from core.admin import PlatformSuperuserAdminMixin

from .models import Notification, NotificationPreference, NotificationRecipient


@admin.register(Notification)
class NotificationAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "title",
        "organization",
        "notification_type",
        "category",
        "priority",
        "recipient_count",
        "created_at",
    )
    list_filter = ("organization", "category", "priority", "notification_type", "created_at")
    search_fields = ("title", "notification_type")
    readonly_fields = [field.name for field in Notification._meta.fields]

    def recipient_count(self, obj):
        return obj.recipients.count()

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NotificationRecipient)
class RecipientAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("notification", "user", "read_at", "archived_at")
    readonly_fields = [field.name for field in NotificationRecipient._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NotificationPreference)
class PreferenceAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("user", "category", "in_app_enabled", "updated_at")
    list_filter = ("category", "in_app_enabled")
