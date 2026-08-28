from django.contrib import admin
from unfold.admin import ModelAdmin

from audit.services import record_event
from core.admin import PlatformSuperuserAdminMixin

from .models import Task, TaskChecklistItem


class ChecklistInline(admin.TabularInline):
    model = TaskChecklistItem
    extra = 0
    readonly_fields = ("is_completed", "completed_at", "completed_by", "created_at", "updated_at")


@admin.register(Task)
class TaskAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("title", "organization", "status", "priority", "assigned_membership", "due_at")
    list_filter = ("organization", "status", "priority")
    search_fields = ("title", "description")
    readonly_fields = (
        "status",
        "completed_at",
        "completed_by",
        "created_by",
        "created_at",
        "updated_at",
    )
    inlines = ()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            organization=obj.organization,
            action="task.updated" if change else "task.created",
            resource=obj,
            description=f"Task {obj.title} saved in administration.",
            request=request,
        )


@admin.register(TaskChecklistItem)
class TaskChecklistItemAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = ("title", "task", "sequence", "is_completed", "completed_at")
    list_filter = ("is_completed", "task__organization")
    readonly_fields = ("is_completed", "completed_at", "completed_by", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            organization=obj.task.organization,
            action="task.checklist_item_updated" if change else "task.checklist_item_added",
            resource=obj.task,
            description=f"Updated checklist progress for {obj.task.title}.",
            request=request,
        )

    def has_delete_permission(self, request, obj=None):
        return False
