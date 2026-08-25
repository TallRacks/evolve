from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import (
    MasterRight,
    PublishingRight,
    RightsParty,
    RoyaltyAllocation,
    RoyaltyStatement,
    RoyaltyStatementLine,
    TrackWork,
    Work,
    WorkContributor,
)


class ReadOnlyAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ContributorInline(TabularInline):
    model = WorkContributor
    extra = 0
    readonly_fields = ("party", "role", "sequence", "notes", "created_at", "updated_at")

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class TrackWorkInline(TabularInline):
    model = TrackWork
    extra = 0
    readonly_fields = ("track", "relationship_type", "created_at")

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Work)
class WorkAdmin(ReadOnlyAdmin):
    list_display = ("title", "organization", "iswc", "status", "updated_at")
    list_filter = ("organization", "status", "language")
    search_fields = ("title", "alternate_title", "iswc", "internal_reference")
    inlines = (TrackWorkInline, ContributorInline)


@admin.register(RightsParty)
class RightsPartyAdmin(ReadOnlyAdmin):
    list_display = ("display_name", "organization", "party_type", "linked_artist", "is_active")
    list_filter = ("organization", "party_type", "is_active")
    search_fields = ("display_name", "external_identifier", "email")


@admin.register(MasterRight)
class MasterRightAdmin(ReadOnlyAdmin):
    list_display = (
        "track",
        "party",
        "ownership_percentage",
        "territory_code",
        "effective_from",
        "effective_to",
    )
    list_filter = ("organization", "territory_code")
    search_fields = ("track__title", "party__display_name")


@admin.register(PublishingRight)
class PublishingRightAdmin(ReadOnlyAdmin):
    list_display = ("work", "party", "right_type", "ownership_percentage", "territory_code")
    list_filter = ("organization", "right_type", "territory_code")
    search_fields = ("work__title", "party__display_name")


class StatementLineInline(TabularInline):
    model = RoyaltyStatementLine
    extra = 0
    readonly_fields = (
        "track",
        "release",
        "artist",
        "rights_basis",
        "gross_amount",
        "deductions",
        "net_amount",
        "sequence",
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RoyaltyStatement)
class RoyaltyStatementAdmin(ReadOnlyAdmin):
    list_display = (
        "statement_reference",
        "organization",
        "source_name",
        "period_start",
        "period_end",
        "currency",
        "calculated_total",
        "status",
    )
    list_filter = ("organization", "status", "currency", "period_end")
    search_fields = ("statement_reference", "source_name")
    inlines = (StatementLineInline,)


@admin.register(RoyaltyAllocation)
class RoyaltyAllocationAdmin(ReadOnlyAdmin):
    list_display = ("statement_line", "party", "right_basis", "percentage", "amount", "created_at")
    list_filter = ("right_basis", "party__organization")
    search_fields = ("party__display_name", "statement_line__statement__statement_reference")
