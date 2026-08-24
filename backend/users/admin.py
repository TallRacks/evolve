from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from unfold.admin import ModelAdmin

from core.admin import PlatformSuperuserAdminMixin

from .models import User


@admin.register(User)
class UserAdmin(PlatformSuperuserAdminMixin, DjangoUserAdmin, ModelAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_active", "is_staff", "is_superuser")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "first_name", "last_name")
    readonly_fields = ("id", "date_joined", "last_login", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        ("Personal information", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
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
