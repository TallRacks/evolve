from decimal import Decimal

from rest_framework import serializers

from finance.models import Invoice, InvoiceLineItem, Payment, PaymentAllocation, FinanceProfile, Quote, QuoteLineItem, EmployeeInvoiceSubmission


class LineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = (
            "id",
            "description",
            "quantity",
            "unit_amount",
            "line_total",
            "sequence",
            "category",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "line_total", "created_at", "updated_at")


class AllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    payment_reference = serializers.CharField(source="payment.payment_reference", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = (
            "id",
            "invoice",
            "invoice_number",
            "payment",
            "payment_reference",
            "amount",
            "created_at",
        )
        read_only_fields = ("id", "created_at", "invoice_number", "payment_reference")


class InvoiceSerializer(serializers.ModelSerializer):
    booking_reference = serializers.CharField(
        source="booking.reference", read_only=True, allow_null=True
    )
    subtotal = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    amount_paid = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    financial_state = serializers.CharField(read_only=True)
    line_items = LineItemSerializer(many=True, read_only=True)
    allocations = AllocationSerializer(many=True, read_only=True)
    proof_document_id = serializers.UUIDField(read_only=True)
    proof_document_name = serializers.CharField(source="proof_document.original_filename", read_only=True, allow_null=True)

    class Meta:
        model = Invoice
        fields = (
            "id",
            "organization",
            "booking",
            "booking_reference",
            "invoice_number",
            "status",
            "financial_state",
            "artist_name_snapshot",
            "billed_to_name",
            "billed_to_email",
            "billed_to_address",
            "issue_date",
            "due_date",
            "currency",
            "subtotal",
            "tax_amount",
            "total_amount",
            "amount_paid",
            "balance_due",
            "internal_notes",
            "customer_notes",
            "issued_at",
            "voided_at",
            "line_items",
            "allocations",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "invoice_number",
            "status",
            "issued_at",
            "voided_at",
            "created_at",
            "updated_at",
        )


class InvoiceCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    booking_id = serializers.UUIDField(required=False, allow_null=True)
    billed_to_name = serializers.CharField(max_length=220)
    billed_to_email = serializers.EmailField(required=False, allow_blank=True, default="")
    billed_to_address = serializers.CharField(
        max_length=2000, required=False, allow_blank=True, default=""
    )
    due_date = serializers.DateField(required=False, allow_null=True)
    currency = serializers.RegexField(r"^[A-Z]{3}$")
    tax_amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0, default=0)
    internal_notes = serializers.CharField(
        max_length=5000, required=False, allow_blank=True, default=""
    )
    customer_notes = serializers.CharField(
        max_length=5000, required=False, allow_blank=True, default=""
    )


class InvoiceUpdateSerializer(serializers.Serializer):
    billed_to_name = serializers.CharField(max_length=220, required=False)
    billed_to_email = serializers.EmailField(required=False, allow_blank=True)
    billed_to_address = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    tax_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0, required=False
    )
    internal_notes = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    customer_notes = serializers.CharField(max_length=5000, required=False, allow_blank=True)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class PaymentSerializer(serializers.ModelSerializer):
    allocated_amount = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    allocations = AllocationSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "organization",
            "payment_reference",
            "status",
            "currency",
            "amount",
            "allocated_amount",
            "remaining_amount",
            "payment_date",
            "method",
            "external_reference",
            "payer_name",
            "notes",
            "proof_document_id",
            "proof_document_name",
            "allocations",
            "voided_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "payment_reference",
            "status",
            "voided_at",
            "created_at",
            "updated_at",
        )


class PaymentCreateSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField()

    class Meta:
        model = Payment
        fields = (
            "organization_id",
            "currency",
            "amount",
            "payment_date",
            "method",
            "external_reference",
            "payer_name",
            "notes",
        )


class AllocateSerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))


class DeveloperInvoiceSerializer(serializers.ModelSerializer):
    booking_reference = serializers.CharField(source="booking.reference", allow_null=True)
    total = serializers.DecimalField(source="total_amount", max_digits=16, decimal_places=2)
    balance = serializers.DecimalField(source="balance_due", max_digits=16, decimal_places=2)
    computed_state = serializers.CharField(source="financial_state")

    class Meta:
        model = Invoice
        fields = (
            "id",
            "invoice_number",
            "booking_reference",
            "status",
            "computed_state",
            "currency",
            "total",
            "balance",
            "issue_date",
            "due_date",
        )


class DeveloperPaymentSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(source="payment_reference")
    date = serializers.DateField(source="payment_date")

    class Meta:
        model = Payment
        fields = ("id", "reference", "currency", "amount", "date", "status")


class FinanceProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceProfile
        exclude = ("organization",)

class QuoteLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteLineItem
        read_only_fields = ("id", "line_total", "created_at", "updated_at")
        fields = "__all__"

class QuoteSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    line_items = QuoteLineItemSerializer(many=True, read_only=True)
    class Meta:
        model = Quote
        fields = "__all__"
        read_only_fields = ("id", "quote_number", "organization", "created_by", "created_at", "updated_at")


class EmployeeInvoiceSubmissionSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.get_full_name", read_only=True)
    employee_email = serializers.EmailField(source="employee.email", read_only=True)

    class Meta:
        model = EmployeeInvoiceSubmission
        fields = (
            "id", "organization", "employee", "employee_name", "employee_email",
            "submission_number", "status", "invoice_date", "currency",
            "line_items", "total_amount", "notes", "settled_invoice",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "organization", "employee", "employee_name", "employee_email",
            "submission_number", "status", "total_amount", "settled_invoice",
            "created_at", "updated_at",
        )


class EmployeeInvoiceCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    invoice_date = serializers.DateField()
    currency = serializers.RegexField(r"^[A-Z]{3}$")
    line_items = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    notes = serializers.CharField(max_length=5000, required=False, allow_blank=True, default="")

    def validate_line_items(self, value):
        cleaned = []
        total = Decimal("0.00")
        for index, item in enumerate(value, start=1):
            description = str(item.get("description", "")).strip()
            if not description:
                raise serializers.ValidationError(f"Line {index} requires a description.")
            try:
                quantity = Decimal(str(item.get("quantity", "1")))
                unit_amount = Decimal(str(item.get("unit_amount", "0")))
            except Exception as exc:
                raise serializers.ValidationError(f"Line {index} has invalid numbers.") from exc
            if quantity <= 0 or unit_amount < 0:
                raise serializers.ValidationError(f"Line {index} must have positive quantity and non-negative amount.")
            line_total = (quantity * unit_amount).quantize(Decimal("0.01"))
            total += line_total
            cleaned.append({"description": description, "quantity": str(quantity), "unit_amount": str(unit_amount), "line_total": str(line_total), "sequence": index})
        self.context["total_amount"] = total
        return cleaned
