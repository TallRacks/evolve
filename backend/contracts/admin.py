from django.contrib import admin
from unfold.admin import ModelAdmin

from core.admin import PlatformSuperuserAdminMixin

from .models import (
    Contract,
    ContractApproval,
    ContractDocument,
    ContractParty,
    ContractSection,
    ContractTerm,
)


class SafeAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Contract)
class ContractAdmin(SafeAdmin):
    list_display = (
        "reference",
        "title",
        "organization",
        "artist",
        "contract_type",
        "status",
        "effective_date",
        "expiry_date",
        "updated_at",
    )
    list_filter = (
        "organization",
        "artist",
        "contract_type",
        "status",
        "effective_date",
        "expiry_date",
    )
    search_fields = (
        "reference",
        "title",
        "artist__stage_name",
        "booking__reference",
        "promoter__name",
    )
    readonly_fields = (
        "reference",
        "status",
        "created_by",
        "archived_at",
        "terminated_at",
        "termination_reason",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        ("Identity", {"fields": ("organization", "reference", "title", "contract_type")}),
        ("Relationships", {"fields": ("artist", "booking", "promoter")}),
        ("Dates", {"fields": ("effective_date", "expiry_date", "signed_date")}),
        ("Legal", {"fields": ("governing_law", "jurisdiction", "currency", "total_value")}),
        ("Status", {"fields": ("status", "archived_at", "terminated_at", "termination_reason")}),
        ("Summary", {"fields": ("summary", "internal_notes")}),
        ("Metadata", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.status == Contract.Status.EXECUTED:
            fields.extend(field.name for field in obj._meta.fields)
        return tuple(set(fields))


class ChildAdmin(SafeAdmin):
    readonly_fields = ("created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.contract.status not in {"draft", "in_review"}:
            fields.extend(field.name for field in obj._meta.fields)
        return tuple(set(fields))


@admin.register(ContractParty)
class PartyAdmin(ChildAdmin):
    list_display = ("contract", "display_name", "role", "is_signatory", "signing_status")
    list_filter = ("contract__organization", "role", "is_signatory", "signing_status")
    search_fields = ("contract__reference", "display_name", "legal_name")
    readonly_fields = ChildAdmin.readonly_fields + ("signing_status", "signed_at", "signing_note")


@admin.register(ContractTerm)
class TermAdmin(ChildAdmin):
    list_display = ("contract", "term_type", "title", "sequence")
    list_filter = ("contract__organization", "term_type")
    search_fields = ("contract__reference", "title")


@admin.register(ContractSection)
class SectionAdmin(ChildAdmin):
    list_display = ("contract", "section_type", "title", "sequence")
    list_filter = ("contract__organization", "section_type")
    search_fields = ("contract__reference", "title")


@admin.register(ContractApproval)
class ApprovalAdmin(SafeAdmin):
    list_display = ("contract", "membership", "status", "requested_at", "decided_at")
    list_filter = ("contract__organization", "status")
    search_fields = ("contract__reference", "membership__user__email")

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)


@admin.register(ContractDocument)
class ContractDocumentAdmin(SafeAdmin):
    list_display = ("contract", "document", "created_at")
    list_filter = ("contract__organization",)
    search_fields = ("contract__reference", "document__title")
