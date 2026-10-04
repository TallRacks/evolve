from django.contrib import admin

from core.admin import PlatformSuperuserAdminMixin

from .models import SigningEvent, SigningRequest


@admin.register(SigningRequest)
class SigningRequestAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("title", "organization", "template_key", "status", "provider", "updated_at")
    list_filter = ("status", "provider", "organization")
    search_fields = ("title", "provider_document_id", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at", "last_event_at")


@admin.register(SigningEvent)
class SigningEventAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("request", "event_type", "status", "provider_event_id", "created_at")
    list_filter = ("status", "event_type")
    search_fields = ("request__title", "provider_event_id", "payload_digest")
    readonly_fields = ("id", "created_at", "updated_at", "payload_digest")
