from django.contrib import admin

from core.admin import PlatformSuperuserAdminMixin
from .channel_models import ChannelVerification, InboundMessage, MailboxAccess, MailboxReply, MailboxSentMessage, MessagingConnector, MessagingIdentity
from .models import ActionRequest, AIProviderConfig, Automation, Board, Workspace


class WorkspaceAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("name", "organization", "archived", "created_at")
    list_filter = ("archived", "organization")
    search_fields = ("name", "slug", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")


class BoardAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("name", "workspace", "source_type", "default_view", "archived")
    list_filter = ("source_type", "default_view", "archived")
    search_fields = ("name", "workspace__name")
    readonly_fields = ("id", "created_at", "updated_at")


class OrganizationAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("__str__", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Workspace)
class RegisteredWorkspaceAdmin(WorkspaceAdmin):
    pass


@admin.register(Board)
class RegisteredBoardAdmin(BoardAdmin):
    pass


@admin.register(AIProviderConfig)
class AIProviderConfigAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("provider_name", "model", "is_active", "status", "last_tested_at")
    list_filter = ("provider_name", "is_active", "status")
    search_fields = ("provider_name", "model", "secret_reference")
    readonly_fields = ("created_at", "updated_at", "last_tested_at")


@admin.register(Automation)
class AutomationAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("name", "event_key", "action_key", "is_active", "organization")
    list_filter = ("is_active", "organization")
    search_fields = ("name", "event_key", "action_key")
    readonly_fields = ("created_at", "updated_at", "last_run_at")


@admin.register(ActionRequest)
class ActionRequestAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("action_key", "organization", "risk", "status", "created_at")
    list_filter = ("risk", "status", "organization")
    search_fields = ("action_key", "result_summary", "idempotency_key")
    readonly_fields = ("id", "actor", "organization", "validated_payload", "confirmation_hash", "created_at", "updated_at", "executed_at")


@admin.register(MessagingConnector)
class MessagingConnectorAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("name", "provider_type", "organization", "is_active", "webhook_status")
    list_filter = ("provider_type", "is_active", "webhook_status")
    search_fields = ("name", "display_name", "display_phone")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(MessagingIdentity)
class MessagingIdentityAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("display_address", "user", "organization", "is_verified", "revoked_at")
    list_filter = ("is_verified", "organization")
    search_fields = ("display_address", "provider_subject", "user__email")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(InboundMessage)
class InboundMessageAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("subject", "sender_address", "channel", "organization", "created_at")
    list_filter = ("channel", "event_type", "organization")
    search_fields = ("subject", "sender_address", "provider_message_id")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(MailboxAccess)
class MailboxAccessAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("connector", "user", "organization", "is_active", "created_at")
    list_filter = ("is_active", "organization")
    search_fields = ("connector__name", "user__email", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(MailboxReply)
class MailboxReplyAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("sender_address", "recipient_address", "subject", "status", "organization", "created_at")
    list_filter = ("status", "organization")
    search_fields = ("sender_address", "recipient_address", "subject")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(MailboxSentMessage)
class MailboxSentMessageAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("subject", "sender_address", "recipient_address", "folder", "status", "organization", "created_at")
    list_filter = ("folder", "status", "organization")
    search_fields = ("subject", "sender_address", "recipient_address")
    readonly_fields = ("id", "created_at", "updated_at", "body_text", "bcc_addresses", "attachment_document_ids", "tagged_user_ids")


@admin.register(ChannelVerification)
class ChannelVerificationAdmin(PlatformSuperuserAdminMixin, admin.ModelAdmin):
    list_display = ("channel", "organization", "user", "expires_at", "used_at")
    list_filter = ("channel", "organization")
    search_fields = ("user__email", "organization__name", "provider_subject")
    readonly_fields = ("id", "connector", "user", "organization", "channel", "code_hash", "expires_at", "used_at", "provider_subject", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
