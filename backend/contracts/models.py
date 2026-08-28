import secrets
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import TimestampedModel

CURRENCY = RegexValidator(r"^[A-Z]{3}$", "Use an uppercase three-letter currency code.")
EDITABLE_STATUSES = {"draft", "in_review"}


def contract_reference():
    return f"CTR-{timezone.now().year}-{secrets.token_hex(4).upper()}"


class Contract(TimestampedModel):
    class Type(models.TextChoices):
        PERFORMANCE = "performance", "Performance"
        ARTIST_SERVICES = "artist_services", "Artist services"
        MANAGEMENT = "management", "Management"
        BOOKING = "booking", "Booking"
        PROMOTER = "promoter", "Promoter"
        VENUE = "venue", "Venue"
        RECORDING = "recording", "Recording"
        RELEASE = "release", "Release"
        LICENSING = "licensing", "Licensing"
        PUBLISHING = "publishing", "Publishing"
        PRODUCTION = "production", "Production"
        SPONSORSHIP = "sponsorship", "Sponsorship"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In review"
        APPROVED = "approved", "Approved"
        SENT = "sent", "Sent"
        PARTIALLY_SIGNED = "partially_signed", "Partially signed"
        EXECUTED = "executed", "Executed"
        TERMINATED = "terminated", "Terminated"
        CANCELLED = "cancelled", "Cancelled"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="contracts"
    )
    title = models.CharField(max_length=220)
    contract_type = models.CharField(max_length=24, choices=Type.choices)
    reference = models.CharField(
        max_length=32, unique=True, default=contract_reference, editable=False
    )
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    artist = models.ForeignKey(
        "artists.Artist", null=True, blank=True, on_delete=models.PROTECT, related_name="contracts"
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contracts",
    )
    promoter = models.ForeignKey(
        "promoters.Promoter",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contracts",
    )
    effective_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    signed_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True, validators=[CURRENCY])
    total_value = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    governing_law = models.CharField(max_length=160, blank=True)
    jurisdiction = models.CharField(max_length=160, blank=True)
    summary = models.TextField(blank=True, max_length=5000)
    internal_notes = models.TextField(blank=True, max_length=5000)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="contracts_created",
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    termination_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [models.Index(fields=("organization", "status", "expiry_date"))]

    @property
    def is_expired(self):
        return bool(
            self.expiry_date
            and self.expiry_date < timezone.localdate()
            and self.status == self.Status.EXECUTED
        )

    def clean(self):
        if self.currency:
            self.currency = self.currency.upper()
        if self.effective_date and self.expiry_date and self.effective_date > self.expiry_date:
            raise ValidationError({"expiry_date": "Expiry date must not precede effective date."})
        for field in ("artist", "booking", "promoter"):
            value = getattr(self, field)
            if value and value.organization_id != self.organization_id:
                raise ValidationError(
                    {field: f"{field.title()} must belong to the Contract organization."}
                )
        if self.booking_id and self.artist_id and self.booking.artist_id != self.artist_id:
            raise ValidationError({"artist": "Contract Artist must match the Booking Artist."})
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
            if old and old.status != self.status:
                raise ValidationError("Use the Contract lifecycle service to change status.")
            if old and old.status == self.Status.EXECUTED:
                protected = (
                    "organization_id",
                    "title",
                    "contract_type",
                    "artist_id",
                    "booking_id",
                    "promoter_id",
                    "effective_date",
                    "expiry_date",
                    "signed_date",
                    "currency",
                    "total_value",
                    "governing_law",
                    "jurisdiction",
                    "summary",
                    "internal_notes",
                )
                if any(getattr(old, field) != getattr(self, field) for field in protected):
                    raise ValidationError("Executed Contract content is immutable.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Contracts cannot be deleted; archive them instead.")

    def __str__(self):
        return f"{self.reference} / {self.title}"


class EditableContractChild(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True

    def ensure_editable(self):
        if self.contract.status not in EDITABLE_STATUSES:
            raise ValidationError("Contract content is editable only in Draft or In review.")

    def save(self, *args, **kwargs):
        self.ensure_editable()
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.ensure_editable()
        return super().delete(*args, **kwargs)


class ContractParty(EditableContractChild):
    class Role(models.TextChoices):
        ARTIST = "artist", "Artist"
        MANAGER = "manager", "Manager"
        PROMOTER = "promoter", "Promoter"
        VENUE = "venue", "Venue"
        LABEL = "label", "Label"
        PUBLISHER = "publisher", "Publisher"
        PRODUCER = "producer", "Producer"
        SPONSOR = "sponsor", "Sponsor"
        CLIENT = "client", "Client"
        AGENT = "agent", "Agent"
        LICENSOR = "licensor", "Licensor"
        LICENSEE = "licensee", "Licensee"
        OTHER = "other", "Other"

    class SigningStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", "Not required"
        PENDING = "pending", "Pending"
        SIGNED = "signed", "Signed"
        DECLINED = "declined", "Declined"

    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="parties")
    role = models.CharField(max_length=20, choices=Role.choices)
    display_name = models.CharField(max_length=220)
    linked_artist = models.ForeignKey(
        "artists.Artist",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contract_parties",
    )
    linked_promoter = models.ForeignKey(
        "promoters.Promoter",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contract_parties",
    )
    linked_contact = models.ForeignKey(
        "contacts.Contact",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contract_parties",
    )
    linked_rights_party = models.ForeignKey(
        "rights.RightsParty",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contract_parties",
    )
    legal_name = models.CharField(max_length=220, blank=True)
    email_snapshot = models.EmailField(blank=True)
    address_snapshot = models.TextField(blank=True, max_length=1000)
    is_signatory = models.BooleanField(default=False)
    signing_status = models.CharField(
        max_length=20, choices=SigningStatus.choices, default=SigningStatus.NOT_REQUIRED
    )
    signing_order = models.PositiveIntegerField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    signing_note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("signing_order", "created_at")

    def clean(self):
        sources = [
            self.linked_artist,
            self.linked_promoter,
            self.linked_contact,
            self.linked_rights_party,
        ]
        if sum(value is not None for value in sources) > 1:
            raise ValidationError("Select at most one linked party source.")
        for value in sources:
            if value and value.organization_id != self.contract.organization_id:
                raise ValidationError("Party source must belong to the Contract organization.")
        if not self.is_signatory and self.signing_status != self.SigningStatus.NOT_REQUIRED:
            raise ValidationError({"signing_status": "Non-signatories must use Not required."})


class ContractTerm(EditableContractChild):
    class Type(models.TextChoices):
        FEE = "fee", "Fee"
        DEPOSIT = "deposit", "Deposit"
        PAYMENT_DUE = "payment_due", "Payment due"
        CANCELLATION = "cancellation", "Cancellation"
        TERM_LENGTH = "term_length", "Term length"
        EXCLUSIVITY = "exclusivity", "Exclusivity"
        TERRITORY = "territory", "Territory"
        NOTICE = "notice", "Notice"
        DELIVERABLE = "deliverable", "Deliverable"
        USAGE_RIGHT = "usage_right", "Usage right"
        COMMISSION = "commission", "Commission"
        OTHER = "other", "Other"

    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="terms")
    term_type = models.CharField(max_length=24, choices=Type.choices)
    title = models.CharField(max_length=220)
    value_text = models.TextField(blank=True, max_length=2000)
    value_decimal = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True, validators=[CURRENCY])
    date_value = models.DateField(null=True, blank=True)
    boolean_value = models.BooleanField(null=True, blank=True)
    notes = models.TextField(blank=True, max_length=2000)
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("sequence", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("contract", "sequence"), name="contract_unique_term_sequence"
            )
        ]

    def clean(self):
        if self.currency:
            self.currency = self.currency.upper()
        if self.currency and self.value_decimal is None:
            raise ValidationError({"currency": "Currency requires a Decimal value."})


class ContractSection(EditableContractChild):
    class Type(models.TextChoices):
        SCOPE = "scope", "Scope"
        PAYMENT = "payment", "Payment"
        CANCELLATION = "cancellation", "Cancellation"
        OBLIGATIONS = "obligations", "Obligations"
        RIGHTS = "rights", "Rights"
        CONFIDENTIALITY = "confidentiality", "Confidentiality"
        TERMINATION = "termination", "Termination"
        OTHER = "other", "Other"

    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="sections")
    section_type = models.CharField(max_length=24, choices=Type.choices)
    title = models.CharField(max_length=220)
    body = models.TextField(max_length=10000)
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("sequence", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("contract", "sequence"), name="contract_unique_section_sequence"
            )
        ]


class ContractApproval(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="approvals")
    membership = models.ForeignKey(
        "organizations.Membership", on_delete=models.PROTECT, related_name="contract_approvals"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    requested_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contract_approval_decisions",
    )
    comment = models.TextField(blank=True, max_length=2000)
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("sequence", "requested_at")
        constraints = [
            models.UniqueConstraint(
                fields=("contract", "membership"),
                condition=Q(status="pending"),
                name="contract_one_pending_approval",
            )
        ]

    def clean(self):
        if self.membership_id and (
            self.membership.organization_id != self.contract.organization_id
            or not self.membership.is_active
            or not self.membership.user.is_active
        ):
            raise ValidationError(
                {"membership": "Approver must have active access to this organization."}
            )

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
            if old and old.status != self.status:
                raise ValidationError("Use the Contract approval service.")
        self.full_clean()
        return super().save(*args, **kwargs)


class ContractDocument(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="document_links")
    document = models.ForeignKey(
        "documents.Document", on_delete=models.PROTECT, related_name="contract_links"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("contract", "document"), name="contract_unique_document_link"
            )
        ]

    def clean(self):
        if self.document_id and self.document.organization_id != self.contract.organization_id:
            raise ValidationError("Document and Contract must belong to the same organization.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
