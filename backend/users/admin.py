from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from unfold.admin import ModelAdmin

from core.admin import PlatformSuperuserAdminMixin

from .admin_forms import OwnerSafeUserChangeForm
from .mobile_services import revoke_all_devices
from .models import SecurityEvent, User


@admin.register(User)
class UserAdmin(PlatformSuperuserAdminMixin, DjangoUserAdmin, ModelAdmin):
    form = OwnerSafeUserChangeForm
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_active", "is_staff", "is_superuser")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "first_name", "last_name")
    date_hierarchy = "date_joined"
    list_per_page = 50
    readonly_fields = ("id", "date_joined", "last_login", "created_at", "updated_at")
    fieldsets = (
        ("Identity", {"fields": ("id", "email", "first_name", "last_name")}),
        ("Security", {"fields": ("password", "last_login")}),
        (
            "Access",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Metadata", {"fields": ("date_joined", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "is_active", "is_staff"),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        was_active = User.objects.filter(pk=obj.pk).values_list("is_active", flat=True).first()
        super().save_model(request, obj, form, change)
        if was_active and not obj.is_active:
            revoke_all_devices(obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SecurityEvent)
class SecurityEventAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("event_type", "user", "success", "ip_address", "occurred_at")
    list_filter = ("event_type", "success")
    search_fields = ("user__email",)
    readonly_fields = ("user", "event_type", "success", "ip_address", "user_agent", "occurred_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
