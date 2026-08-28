from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import EmailConnector, StorageProvider


class PlatformConfigurationAdmin(ModelAdmin):
    readonly_fields = (
        "id",
        "connection_status",
        "last_tested_at",
        "last_test_message",
        "created_at",
        "updated_at",
    )

    def has_module_permission(self, request):
        return bool(request.user.is_active and request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmailConnector)
class EmailConnectorAdmin(PlatformConfigurationAdmin):
    list_display = (
        "name",
        "from_email",
        "is_active",
        "is_default",
        "connection_status",
        "last_tested_at",
    )
    fields = (
        "id",
        "name",
        "provider_type",
        "from_name",
        "from_email",
        "reply_to_email",
        "host",
        "port",
        "use_tls",
        "use_ssl",
        "username",
        "secret_reference",
        "is_active",
        "is_default",
        "connection_status",
        "last_tested_at",
        "last_test_message",
        "created_at",
        "updated_at",
    )


@admin.register(StorageProvider)
class StorageProviderAdmin(PlatformConfigurationAdmin):
    list_display = (
        "name",
        "provider_type",
        "bucket",
        "region",
        "is_active",
        "is_default",
        "connection_status",
    )
    fields = (
        "id",
        "name",
        "provider_type",
        "endpoint",
        "region",
        "bucket",
        "path_prefix",
        "public_base_url",
        "access_key_reference",
        "secret_key_reference",
        "use_ssl",
        "is_active",
        "is_default",
        "connection_status",
        "last_tested_at",
        "last_test_message",
        "created_at",
        "updated_at",
    )
