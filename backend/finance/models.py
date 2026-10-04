import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from core.models import TimestampedModel

CURRENCY_VALIDATOR = RegexValidator(r"^[A-Z]{3}$", "Use a three-letter uppercase currency code.")


def reference(prefix):
    return f"{prefix}-{timezone.now().year}-{uuid.uuid4().hex[:10].upper()}"


def invoice_reference():
    return reference("INV")


def payment_reference():
    return reference("PAY")


class Invoice(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        VOID = "void", "Void"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="invoices"
    )
    booking = models.ForeignKey(
        "bookings.Booking", null=True, blank=True, on_delete=models.PROTECT, related_name="invoices"
    )
    invoice_number = models.CharField(
        max_length=32, unique=True, default=invoice_reference, editable=False
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    artist_name_snapshot = models.CharField(max_length=220, blank=True)
    billed_to_name = models.CharField(max_length=220)
    billed_to_email = models.EmailField(blank=True)
    billed_to_address = models.TextField(blank=True, max_length=2000)
    issue_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, validators=[CURRENCY_VALIDATOR])
    tax_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    internal_notes = models.TextField(blank=True, max_length=5000)
    customer_notes = models.TextField(blank=True, max_length=5000)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="invoices_created",
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices_issued",
    )
    issued_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices_voided",
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("organization", "status", "due_date")),
            models.Index(fields=("booking", "created_at")),
        ]

    def clean(self):
        if self.booking_id and self.booking.organization_id != self.organization_id:
            raise ValidationError("Invoice and Booking must belong to the same organization.")
        if self.currency:
            self.currency = self.currency.upper()
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.status != self.status:
                raise ValidationError("Invoice lifecycle changes require the Finance service.")
            if previous and previous.status != self.Status.DRAFT:
                protected = (
                    "organization_id",
                    "booking_id",
                    "artist_name_snapshot",
                    "billed_to_name",
                    "billed_to_email",
                    "billed_to_address",
                    "issue_date",
                    "due_date",
                    "currency",
                    "tax_amount",
                    "customer_notes",
                )
                if any(getattr(previous, field) != getattr(self, field) for field in protected):
                    raise ValidationError("Issued financial values are immutable.")

    @property
    def subtotal(self):
        return self.line_items.aggregate(total=Sum("line_total"))["total"] or Decimal("0.00")

    @property
    def total_amount(self):
        return self.subtotal + self.tax_amount

    @property
    def amount_paid(self):
        return self.allocations.filter(payment__status=Payment.Status.RECORDED).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid

    @property
    def financial_state(self):
        if self.status in (self.Status.VOID, self.Status.CANCELLED):
            return self.status
        if self.status == self.Status.DRAFT:
            return "draft"
        if self.balance_due <= 0:
            return "paid"
        if self.amount_paid > 0:
            return "partially_paid"
        if self.due_date and self.due_date < timezone.localdate():
            return "overdue"
        return "unpaid"

    def delete(self, *args, **kwargs):
        raise ValidationError("Invoices cannot be deleted.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.invoice_number


class InvoiceLineItem(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="line_items")
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(
        max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )
    unit_amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(0)]
    )
    line_total = models.DecimalField(max_digits=16, decimal_places=2, editable=False)
    sequence = models.PositiveIntegerField(default=1)
    category = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ("sequence", "created_at")
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="finance_line_quantity_positive"
            ),
            models.CheckConstraint(
                condition=Q(unit_amount__gte=0), name="finance_line_amount_nonnegative"
            ),
        ]

    def save(self, *args, **kwargs):
        if Invoice.objects.only("status").get(pk=self.invoice_id).status != Invoice.Status.DRAFT:
            raise ValidationError("Line items are editable only while the invoice is draft.")
        quantity = Decimal(str(self.quantity))
        unit_amount = Decimal(str(self.unit_amount))
        self.line_total = (quantity * unit_amount).quantize(Decimal("0.01"))
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if Invoice.objects.only("status").get(pk=self.invoice_id).status != Invoice.Status.DRAFT:
            raise ValidationError("Issued invoice line items cannot be deleted.")
        return super().delete(*args, **kwargs)


class Payment(TimestampedModel):
    class Status(models.TextChoices):
        RECORDED = "recorded", "Recorded"
        VOID = "void", "Void"

    class Method(models.TextChoices):
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        CARD_EXTERNAL = "card_external", "External card"
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile money"
        CHEQUE = "cheque", "Cheque"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="payments"
    )
    payment_reference = models.CharField(
        max_length=32, unique=True, default=payment_reference, editable=False
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECORDED)
    currency = models.CharField(max_length=3, validators=[CURRENCY_VALIDATOR])
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    payment_date = models.DateField()
    method = models.CharField(max_length=24, choices=Method.choices)
    external_reference = models.CharField(max_length=180, blank=True)
    payer_name = models.CharField(max_length=220, blank=True)
    notes = models.TextField(blank=True, max_length=3000)
    proof_document = models.ForeignKey(
        "documents.Document", null=True, blank=True, on_delete=models.PROTECT,
        related_name="payment_proofs",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="payments_recorded",
    )
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments_voided",
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-payment_date", "-created_at")
        indexes = [models.Index(fields=("organization", "status", "payment_date"))]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="finance_payment_amount_positive"
            )
        ]

    def clean(self):
        if self.currency:
            self.currency = self.currency.upper()
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and (
                previous.status != self.status
                or previous.amount != self.amount
                or previous.currency != self.currency
                or previous.organization_id != self.organization_id
            ):
                raise ValidationError("Payment financial changes require the Finance service.")

    @property
    def allocated_amount(self):
        return self.allocations.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    @property
    def remaining_amount(self):
        return self.amount - self.allocated_amount

    def delete(self, *args, **kwargs):
        raise ValidationError("Payments cannot be deleted.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.payment_reference


class PaymentAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="allocations")
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="allocations")
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="payment_allocations_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="finance_allocation_amount_positive"
            )
        ]

    def __str__(self):
        return f"{self.payment} -> {self.invoice}"

    def delete(self, *args, **kwargs):
        raise ValidationError("Payment allocations cannot be deleted in this milestone.")


class FinanceProfile(TimestampedModel):
    organization = models.OneToOneField("organizations.Organization", on_delete=models.PROTECT, related_name="finance_profile")
    legal_name = models.CharField(max_length=220, blank=True)
    registration_number = models.CharField(max_length=120, blank=True)
    tax_number = models.CharField(max_length=120, blank=True)
    billing_email = models.EmailField(blank=True)
    billing_address = models.TextField(blank=True, max_length=2000)
    payment_terms = models.CharField(max_length=120, default="Due within 30 days")
    invoice_prefix = models.CharField(max_length=12, default="INV")
    quote_prefix = models.CharField(max_length=12, default="QUO")
    next_invoice_number = models.PositiveIntegerField(default=1)
    next_quote_number = models.PositiveIntegerField(default=1)
    default_currency = models.CharField(max_length=3, default="ZAR", validators=[CURRENCY_VALIDATOR])

class Quote(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        EXPIRED = "expired", "Expired"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="quotes")
    quote_number = models.CharField(max_length=32, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    billed_to_name = models.CharField(max_length=220)
    billed_to_email = models.EmailField(blank=True)
    currency = models.CharField(max_length=3, validators=[CURRENCY_VALIDATOR])
    valid_until = models.DateField(null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True, max_length=5000)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    @property
    def subtotal(self):
        return self.line_items.aggregate(total=Sum("line_total"))["total"] or Decimal("0.00")
    @property
    def total_amount(self):
        return self.subtotal + self.tax_amount

class QuoteLineItem(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quote = models.ForeignKey(Quote, on_delete=models.PROTECT, related_name="line_items")
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    unit_amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    line_total = models.DecimalField(max_digits=16, decimal_places=2, editable=False)
    sequence = models.PositiveIntegerField(default=1)
    def save(self,*args,**kwargs):
        self.line_total=(Decimal(str(self.quantity))*Decimal(str(self.unit_amount))).quantize(Decimal("0.01"))
        self.full_clean()
        super().save(*args,**kwargs)

class EmployeeInvoiceSubmission(TimestampedModel):
    class Status(models.TextChoices):
        SUBMITTED="submitted","Submitted"
        REVIEW="review","Under review"
        APPROVED="approved","Approved"
        SETTLED="settled","Settled"
        REJECTED="rejected","Rejected"
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    organization=models.ForeignKey("organizations.Organization",on_delete=models.PROTECT,related_name="employee_invoice_submissions")
    employee=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="invoice_submissions")
    submission_number=models.CharField(max_length=32,unique=True)
    status=models.CharField(max_length=16,choices=Status.choices,default=Status.SUBMITTED)
    invoice_date=models.DateField()
    currency=models.CharField(max_length=3,validators=[CURRENCY_VALIDATOR])
    line_items=models.JSONField(default=list)
    total_amount=models.DecimalField(max_digits=16,decimal_places=2,default=0)
    notes=models.TextField(blank=True,max_length=5000)
    settled_invoice=models.ForeignKey(Invoice,null=True,blank=True,on_delete=models.PROTECT,related_name="employee_submissions")
