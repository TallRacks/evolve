from django.contrib import admin
from unfold.admin import ModelAdmin

from audit.services import record_event
from core.admin import PlatformSuperuserAdminMixin

from .models import Document, DocumentLink, DocumentTemplate, DocumentTemplateSection
from .services import archive_document


@admin.register(Document)
class DocumentAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "title",
        "organization",
        "document_type",
        "visibility",
        "status",
        "version_number",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("organization", "document_type", "visibility", "status")
    search_fields = ("title", "original_filename")
    readonly_fields = (
        "storage_key",
        "checksum_sha256",
        "status",
        "uploaded_by",
        "archived_at",
        "created_at",
        "updated_at",
    )
    actions = ("archive_documents",)
    fieldsets = (
        (
            "Document",
            {
                "fields": (
                    "organization",
                    "title",
                    "document_type",
                    "description",
                    "visibility",
                    "status",
                )
            },
        ),
        (
            "External file metadata",
            {
                "fields": (
                    "external_url",
                    "original_filename",
                    "content_type",
                    "file_size",
                    "storage_key",
                    "checksum_sha256",
                )
            },
        ),
        ("Version", {"fields": ("version_number", "parent_document")}),
        ("Audit", {"fields": ("uploaded_by", "archived_at", "created_at", "updated_at")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by_id:
            obj.uploaded_by = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            organization=obj.organization,
            action="document.updated" if change else "document.created",
            resource=obj,
            description="Document metadata saved in administration.",
            request=request,
        )

    @admin.action(description="Archive selected documents")
    def archive_documents(self, request, queryset):
        for obj in queryset.exclude(status=Document.Status.ARCHIVED):
            archive_document(obj, actor=request.user, request=request)


@admin.register(DocumentLink)
class DocumentLinkAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("document", "entity_type", "entity", "created_at")
    list_filter = ("document__organization",)
    readonly_fields = ("created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            organization=obj.document.organization,
            action="document.linked",
            resource=obj.document,
            description=f"Document linked to {obj.entity_type} in administration.",
            request=request,
        )


class DocumentTemplateSectionInline(admin.TabularInline):
    model = DocumentTemplateSection
    extra = 0
    fields = ("key", "title", "body", "sequence", "is_enabled")


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("name", "organization", "document_type", "status", "version", "updated_at")
    list_filter = ("organization", "document_type", "status")
    search_fields = ("name", "key")
    readonly_fields = ("status", "version", "created_by", "created_at", "updated_at")
    actions = ("activate_templates", "deactivate_templates")
    inlines = (DocumentTemplateSectionInline,)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Activate selected templates")
    def activate_templates(self, request, queryset):
        from .template_services import set_template_status

        for template in queryset:
            set_template_status(
                actor=request.user,
                template=template,
                status=DocumentTemplate.Status.ACTIVE,
                request=request,
            )

    @admin.action(description="Deactivate selected templates")
    def deactivate_templates(self, request, queryset):
        from .template_services import set_template_status

        for template in queryset:
            set_template_status(
                actor=request.user,
                template=template,
                status=DocumentTemplate.Status.INACTIVE,
                request=request,
            )

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        if change:
            obj.version += 1
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            organization=obj.organization,
            action="template.updated" if change else "template.created",
            resource=obj,
            description=f"Document template {obj.name} saved in administration.",
            request=request,
        )


@admin.register(DocumentTemplateSection)
class DocumentTemplateSectionAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("title", "template", "sequence", "is_enabled")

    def has_delete_permission(self, request, obj=None):
        return False
