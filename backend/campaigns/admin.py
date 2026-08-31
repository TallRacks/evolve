from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from unfold.admin import ModelAdmin

from audit.services import record_event
from core.admin import PlatformSuperuserAdminMixin

from .models import (
    Campaign,
    CampaignChannel,
    CampaignResponsibility,
    Rollout,
    RolloutMilestone,
    RolloutTask,
    RolloutTaskDependency,
)
from .services import complete_task, transition_campaign, transition_rollout, transition_task


class SafeAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
        if isinstance(obj, Campaign):
            organization, resource, prefix = obj.organization, obj, "campaign"
        elif isinstance(obj, Rollout):
            organization, resource, prefix = obj.organization, obj, "rollout"
        elif isinstance(obj, CampaignChannel | CampaignResponsibility):
            organization, resource, prefix = (
                obj.campaign.organization,
                obj.campaign,
                "campaign.responsibility"
                if isinstance(obj, CampaignResponsibility)
                else "campaign.channel",
            )
        else:
            rollout = obj.rollout if hasattr(obj, "rollout") else obj.task.rollout
            organization, resource, prefix = (
                rollout.organization,
                rollout,
                (
                    "rollout.task"
                    if isinstance(obj, RolloutTask)
                    else "rollout.milestone"
                    if isinstance(obj, RolloutMilestone)
                    else "rollout.dependency"
                ),
            )
        if isinstance(obj, CampaignResponsibility):
            action = f"campaign.responsibility_{'updated' if change else 'assigned'}"
        elif isinstance(obj, CampaignChannel):
            action = "campaign.channel_added" if not change else "campaign.channel_updated"
        elif isinstance(obj, RolloutTaskDependency):
            action = "rollout.dependency_added" if not change else "rollout.dependency_updated"
        else:
            action = f"{prefix}.{'updated' if change else 'created'}"
        record_event(
            actor=request.user,
            organization=organization,
            action=action,
            resource=resource,
            description=f"{'Updated' if change else 'Created'} {obj._meta.verbose_name} in admin.",
            request=request,
        )


@admin.register(Campaign)
class CampaignAdmin(SafeAdmin):
    list_display = (
        "name",
        "organization",
        "artist",
        "release",
        "objective",
        "status",
        "owner_membership",
        "start_date",
        "end_date",
    )
    list_filter = ("organization", "artist", "objective", "status")
    search_fields = ("name", "artist__stage_name", "release__title")
    autocomplete_fields = ("organization", "artist", "release", "owner_membership", "created_by")
    readonly_fields = ("id", "status", "created_at", "updated_at")
    actions = ("plan", "activate", "pause", "complete", "cancel", "archive")
    fieldsets = (
        ("Identity", {"fields": ("id", "organization", "artist", "release", "name", "slug")}),
        ("Strategy", {"fields": ("objective", "target_audience", "summary", "priority")}),
        ("Timeline", {"fields": ("start_date", "end_date")}),
        ("Ownership", {"fields": ("owner_membership",)}),
        ("Lifecycle", {"fields": ("status",)}),
        ("Metadata", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    def _go(self, r, q, s):
        for x in q:
            try:
                transition_campaign(actor=r.user, campaign=x, to_status=s, request=r)
            except ValidationError as e:
                self.message_user(r, "; ".join(e.messages), messages.ERROR)

    @admin.action(description="Plan selected")
    def plan(self, r, q):
        self._go(r, q, Campaign.Status.PLANNED)

    @admin.action(description="Activate selected")
    def activate(self, r, q):
        self._go(r, q, Campaign.Status.ACTIVE)

    @admin.action(description="Pause selected")
    def pause(self, r, q):
        self._go(r, q, Campaign.Status.PAUSED)

    @admin.action(description="Complete selected")
    def complete(self, r, q):
        self._go(r, q, Campaign.Status.COMPLETED)

    @admin.action(description="Cancel selected")
    def cancel(self, r, q):
        self._go(r, q, Campaign.Status.CANCELLED)

    @admin.action(description="Archive selected")
    def archive(self, r, q):
        self._go(r, q, Campaign.Status.ARCHIVED)


@admin.register(Rollout)
class RolloutAdmin(SafeAdmin):
    list_display = (
        "name",
        "campaign",
        "organization",
        "status",
        "owner_membership",
        "start_date",
        "end_date",
        "progress",
    )
    list_filter = ("organization", "status")
    search_fields = ("name", "campaign__name")
    autocomplete_fields = ("organization", "campaign", "owner_membership", "created_by")
    readonly_fields = ("id", "status", "created_at", "updated_at")
    actions = ("activate", "complete", "cancel", "archive")

    def _go(self, r, q, s):
        for x in q:
            try:
                transition_rollout(actor=r.user, rollout=x, to_status=s, request=r)
            except ValidationError as e:
                self.message_user(r, "; ".join(e.messages), messages.ERROR)

    def activate(self, r, q):
        self._go(r, q, Rollout.Status.ACTIVE)

    def complete(self, r, q):
        self._go(r, q, Rollout.Status.COMPLETED)

    def cancel(self, r, q):
        self._go(r, q, Rollout.Status.CANCELLED)

    def archive(self, r, q):
        self._go(r, q, Rollout.Status.ARCHIVED)


@admin.register(RolloutTask)
class TaskAdmin(SafeAdmin):
    list_display = (
        "title",
        "rollout",
        "milestone",
        "assigned_membership",
        "due_date",
        "priority",
        "status",
    )
    list_filter = ("rollout__organization", "status", "priority", "due_date")
    search_fields = ("title", "rollout__name", "rollout__campaign__name")
    autocomplete_fields = ("rollout", "milestone", "assigned_membership", "completed_by")
    readonly_fields = ("id", "status", "completed_at", "completed_by", "created_at", "updated_at")
    actions = ("start", "block", "finish", "cancel")

    def _go(self, r, q, s):
        for x in q:
            try:
                complete_task(
                    actor=r.user, task=x, request=r
                ) if s == RolloutTask.Status.DONE else transition_task(
                    actor=r.user, task=x, to_status=s, request=r
                )
            except ValidationError as e:
                self.message_user(r, "; ".join(e.messages), messages.ERROR)

    def start(self, r, q):
        self._go(r, q, RolloutTask.Status.IN_PROGRESS)

    def block(self, r, q):
        self._go(r, q, RolloutTask.Status.BLOCKED)

    def finish(self, r, q):
        self._go(r, q, RolloutTask.Status.DONE)

    def cancel(self, r, q):
        self._go(r, q, RolloutTask.Status.CANCELLED)


@admin.register(RolloutMilestone)
class MilestoneAdmin(SafeAdmin):
    list_display = ("title", "rollout", "target_date", "status", "sequence", "owner_membership")
    list_filter = ("rollout__organization", "status")
    search_fields = ("title", "rollout__name")
    autocomplete_fields = ("rollout", "owner_membership")


@admin.register(CampaignChannel)
class ChannelAdmin(SafeAdmin):
    list_display = ("campaign", "channel", "is_primary")
    list_filter = ("campaign__organization", "channel", "is_primary")
    search_fields = ("campaign__name",)
    autocomplete_fields = ("campaign",)


@admin.register(RolloutTaskDependency)
class DependencyAdmin(SafeAdmin):
    list_display = ("task", "depends_on", "created_at")
    autocomplete_fields = ("task", "depends_on")


@admin.register(CampaignResponsibility)
class ResponsibilityAdmin(SafeAdmin):
    list_display = ("campaign", "phase", "role", "membership", "created_at")
    list_filter = ("campaign__organization", "phase", "role")
    search_fields = (
        "campaign__name",
        "phase",
        "membership__user__email",
        "membership__user__first_name",
        "membership__user__last_name",
    )
    autocomplete_fields = ("campaign", "membership")
    readonly_fields = ("id", "created_at", "updated_at")
