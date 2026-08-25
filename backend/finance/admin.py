from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from core.admin import PlatformSuperuserAdminMixin

from .models import Invoice, InvoiceLineItem, Payment, PaymentAllocation


class ReadOnlyFinanceAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LineItemInline(TabularInline):
    model = InvoiceLineItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "description",
        "quantity",
        "unit_amount",
        "line_total",
        "sequence",
        "category",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Invoice)
class InvoiceAdmin(ReadOnlyFinanceAdmin):
    list_display = (
        "invoice_number",
        "organization",
        "booking",
        "billed_to_name",
        "status",
        "computed_status",
        "currency",
        "total",
        "balance",
        "issue_date",
        "due_date",
    )
    list_filter = ("organization", "status", "currency", "issue_date", "due_date")
    search_fields = (
        "invoice_number",
        "booking__reference",
        "booking__artist__stage_name",
        "billed_to_name",
    )
    readonly_fields = [field.name for field in Invoice._meta.fields] + [
        "subtotal",
        "total_amount",
        "amount_paid",
        "balance_due",
        "financial_state",
    ]
    inlines = (LineItemInline,)

    @admin.display(description="Financial state")
    def computed_status(self, obj):
        return obj.financial_state

    def total(self, obj):
        return obj.total_amount

    def balance(self, obj):
        return obj.balance_due


@admin.register(Payment)
class PaymentAdmin(ReadOnlyFinanceAdmin):
    list_display = (
        "payment_reference",
        "organization",
        "amount",
        "currency",
        "method",
        "payment_date",
        "status",
        "allocated",
        "remaining",
    )
    list_filter = ("organization", "status", "method", "currency", "payment_date")
    search_fields = ("payment_reference", "external_reference", "payer_name")
    readonly_fields = [field.name for field in Payment._meta.fields] + [
        "allocated_amount",
        "remaining_amount",
    ]

    def allocated(self, obj):
        return obj.allocated_amount

    def remaining(self, obj):
        return obj.remaining_amount


@admin.register(PaymentAllocation)
class AllocationAdmin(ReadOnlyFinanceAdmin):
    list_display = ("payment", "invoice", "amount", "created_by", "created_at")
    list_filter = ("payment__organization", "payment__currency", "created_at")
    readonly_fields = [field.name for field in PaymentAllocation._meta.fields]
