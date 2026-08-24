class PlatformSuperuserAdminMixin:
    """Restrict platform-wide admin models to platform superusers."""

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from audit.services import record_event

        organization = getattr(obj, "organization", None)
        if obj.__class__.__name__ == "Organization":
            organization = obj
        record_event(
            actor=request.user,
            organization=organization,
            action=f"admin.{obj.__class__.__name__.lower()}.{'updated' if change else 'created'}",
            resource=obj,
            description=f"{'Updated' if change else 'Created'} {obj.__class__.__name__} in admin.",
            request=request,
        )
