import re
import secrets
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from core.models import TimestampedModel

PERCENT = Decimal("0.0001")
ISWC = RegexValidator(r"^T\d{10}$", "ISWC must use normalized T followed by 10 digits.")
CURRENCY = RegexValidator(r"^[A-Z]{3}$", "Use an uppercase three-letter currency code.")
TERRITORY = RegexValidator(
    r"^(WORLDWIDE|[A-Z]{2})$", "Use WORLDWIDE or an ISO-style country code."
)


def statement_reference():
    return f"ROY-{timezone.now().year}-{secrets.token_hex(5).upper()}"


class Work(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="works"
    )
    title = models.CharField(max_length=220)
    alternate_title = models.CharField(max_length=220, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    iswc = models.CharField(max_length=11, blank=True, validators=[ISWC])
    internal_reference = models.CharField(max_length=80, blank=True)
    language = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True, max_length=5000)
    source_document = models.ForeignKey(
        "documents.Document",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="works",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="works_created",
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("title",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "iswc"),
                condition=~Q(iswc=""),
                name="rights_unique_work_iswc_org",
            )
        ]

    def save(self, *args, **kwargs):
        self.iswc = re.sub(r"[-.\s]", "", self.iswc).upper()
        if self.pk:
            old = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )
            if old and old != self.status:
                raise ValidationError("Use the Work archive service.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def clean(self):
        if (
            self.source_document_id
            and self.source_document.organization_id != self.organization_id
        ):
            raise ValidationError("Work Document must belong to the organization.")

    def delete(self, *args, **kwargs):
        raise ValidationError("Works cannot be deleted; archive them instead.")

    def __str__(self):
        return self.title


class TrackWork(models.Model):
    class Relationship(models.TextChoices):
        PRIMARY = "primary", "Primary"
        MEDLEY = "medley", "Medley"
        ADAPTATION = "adaptation", "Adaptation"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    track = models.ForeignKey(
        "music.Track", on_delete=models.PROTECT, related_name="work_links"
    )
    work = models.ForeignKey(Work, on_delete=models.PROTECT, related_name="track_links")
    relationship_type = models.CharField(
        max_length=16, choices=Relationship.choices, default=Relationship.PRIMARY
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("track", "work"), name="rights_unique_track_work"
            )
        ]

    def __str__(self):
        return f"{self.track} / {self.work}"

    def clean(self):
        if (
            self.track_id
            and self.work_id
            and self.track.organization_id != self.work.organization_id
        ):
            raise ValidationError(
                "Track and Work must belong to the same organization."
            )

    def save(self, *args, **kwargs):  # noqa: DJ012
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Track/Work links are retained; archive the Work instead."
        )


class RightsParty(TimestampedModel):
    class Type(models.TextChoices):
        ARTIST = "artist", "Artist"
        SONGWRITER = "songwriter", "Songwriter"
        PRODUCER = "producer", "Producer"
        PUBLISHER = "publisher", "Publisher"
        LABEL = "label", "Label"
        COMPANY = "company", "Company"
        ESTATE = "estate", "Estate"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="rights_parties",
    )
    party_type = models.CharField(max_length=20, choices=Type.choices)
    display_name = models.CharField(max_length=220)
    linked_artist = models.ForeignKey(
        "artists.Artist",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rights_parties",
    )
    linked_contact = models.ForeignKey(
        "contacts.Contact",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rights_parties",
    )
    external_identifier = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True, max_length=5000)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("display_name",)

    def clean(self):
        for related in (self.linked_artist, self.linked_contact):
            if related and related.organization_id != self.organization_id:
                raise ValidationError(
                    "Rights Party links must remain in one organization."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Rights Parties cannot be deleted; deactivate them instead."
        )

    def __str__(self):
        return self.display_name


class WorkContributor(TimestampedModel):
    class Role(models.TextChoices):
        SONGWRITER = "songwriter", "Songwriter"
        COMPOSER = "composer", "Composer"
        LYRICIST = "lyricist", "Lyricist"
        ARRANGER = "arranger", "Arranger"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work = models.ForeignKey(
        Work, on_delete=models.PROTECT, related_name="contributors"
    )
    party = models.ForeignKey(
        RightsParty, on_delete=models.PROTECT, related_name="work_contributions"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    share_percentage = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=0,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    sequence = models.PositiveIntegerField(default=1)
    notes = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("sequence", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("work", "party", "role"), name="rights_unique_work_contributor"
            )
        ]

    def __str__(self):
        return f"{self.statement_line} / {self.party}"

    def clean(self):
        if (
            self.work_id
            and self.party_id
            and self.work.organization_id != self.party.organization_id
        ):
            raise ValidationError(
                "Contributor relationships must remain in one organization."
            )
        if self.work_id and self.share_percentage:
            total = sum(
                (
                    row.share_percentage
                    for row in type(self).objects.filter(work_id=self.work_id).exclude(pk=self.pk)
                ),
                Decimal("0"),
            )
            if total + self.share_percentage > Decimal("100"):
                raise ValidationError("Split-sheet contributor shares cannot exceed 100%.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class OwnershipBase(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT
    )
    party = models.ForeignKey(RightsParty, on_delete=models.PROTECT)
    ownership_percentage = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        validators=[MinValueValidator(PERCENT), MaxValueValidator(Decimal("100"))],
    )
    territory_code = models.CharField(
        max_length=10, default="WORLDWIDE", validators=[TERRITORY]
    )
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, max_length=2000)

    class Meta:
        abstract = True

    def clean_period(self):
        self.territory_code = self.territory_code.upper()
        if (
            self.effective_from
            and self.effective_to
            and self.effective_from > self.effective_to
        ):
            raise ValidationError(
                {"effective_to": "Effective end must not precede start."}
            )
        if self.party_id and self.party.organization_id != self.organization_id:
            raise ValidationError("Ownership party must belong to the organization.")

    def overlaps(self, other):
        return (
            not self.effective_to
            or not other.effective_from
            or self.effective_to >= other.effective_from
        ) and (
            not other.effective_to
            or not self.effective_from
            or other.effective_to >= self.effective_from
        )

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Ownership records cannot be deleted; use effective dates."
        )


class MasterRight(OwnershipBase):
    track = models.ForeignKey(
        "music.Track", on_delete=models.PROTECT, related_name="master_rights"
    )

    def clean(self):
        self.clean_period()
        if self.track_id and self.track.organization_id != self.organization_id:
            raise ValidationError(
                "Master Right and Track must belong to the same organization."
            )
        if self.track_id and self.ownership_percentage:
            rows = type(self).objects.filter(track_id=self.track_id).exclude(pk=self.pk)
            total = sum(
                (
                    row.ownership_percentage
                    for row in rows
                    if self.overlaps(row)
                    and (
                        self.territory_code == row.territory_code
                        or "WORLDWIDE" in (self.territory_code, row.territory_code)
                    )
                ),
                Decimal("0"),
            )
            if total + self.ownership_percentage > Decimal("100"):
                raise ValidationError("Applicable Master ownership cannot exceed 100%.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.track} / {self.party} / {self.ownership_percentage}%"


class PublishingRight(OwnershipBase):
    class Type(models.TextChoices):
        WRITER = "writer", "Writer"
        PUBLISHER = "publisher", "Publisher"
        ADMINISTRATOR = "administrator", "Administrator"
        OTHER = "other", "Other"

    work = models.ForeignKey(
        Work, on_delete=models.PROTECT, related_name="publishing_rights"
    )
    right_type = models.CharField(max_length=20, choices=Type.choices)

    def clean(self):
        self.clean_period()
        if self.work_id and self.work.organization_id != self.organization_id:
            raise ValidationError(
                "Publishing Right and Work must belong to the same organization."
            )
        if self.work_id and self.ownership_percentage:
            rows = type(self).objects.filter(work_id=self.work_id).exclude(pk=self.pk)
            total = sum(
                (
                    row.ownership_percentage
                    for row in rows
                    if self.overlaps(row)
                    and (
                        self.territory_code == row.territory_code
                        or "WORLDWIDE" in (self.territory_code, row.territory_code)
                    )
                ),
                Decimal("0"),
            )
            if total + self.ownership_percentage > Decimal("100"):
                raise ValidationError(
                    "Applicable Publishing ownership cannot exceed 100%."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.work} / {self.party} / {self.ownership_percentage}%"


class RoyaltySource(TimestampedModel):
    class Type(models.TextChoices):
        DISTRIBUTOR = "distributor", "Distributor"
        LABEL = "label", "Label"
        PUBLISHER = "publisher", "Publisher"
        SOCIETY = "society", "Collection society"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="royalty_sources")
    name = models.CharField(max_length=220)
    source_type = models.CharField(max_length=24, choices=Type.choices, default=Type.DISTRIBUTOR)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, max_length=2000)

    class Meta:
        ordering = ("name",)
        constraints = [models.UniqueConstraint(fields=("organization", "name"), name="unique_royalty_source_name")]



class RoyaltyStatement(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        FINALIZED = "finalized", "Finalized"
        VOID = "void", "Void"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="royalty_statements",
    )
    statement_reference = models.CharField(
        max_length=32, unique=True, default=statement_reference, editable=False
    )
    source_name = models.CharField(max_length=220)
    source_type = models.CharField(max_length=24, default="distributor")
    source = models.ForeignKey(RoyaltySource, null=True, blank=True, on_delete=models.PROTECT, related_name="statements")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    period_start = models.DateField()
    period_end = models.DateField()
    currency = models.CharField(max_length=3, validators=[CURRENCY])
    declared_total = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    source_document = models.ForeignKey(
        "documents.Document",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="royalty_statements",
    )
    internal_notes = models.TextField(blank=True, max_length=5000)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="royalty_statements_created",
    )
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="royalty_statements_finalized",
    )
    finalized_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="royalty_statements_voided",
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-period_end", "-created_at")

    def clean(self):
        self.currency = self.currency.upper()
        if (
            self.period_start
            and self.period_end
            and self.period_start > self.period_end
        ):
            raise ValidationError(
                {"period_end": "Statement period end must not precede start."}
            )
        if (
            self.source_document_id
            and self.source_document.organization_id != self.organization_id
        ):
            raise ValidationError("Statement Document must belong to the organization.")
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
            if old and old.status != self.status:
                raise ValidationError("Use the Royalty Statement lifecycle service.")
            if old and old.status != self.Status.DRAFT:
                protected = (
                    "organization_id",
                    "source_name",
                    "period_start",
                    "period_end",
                    "currency",
                    "declared_total",
                    "source_document_id",
                    "internal_notes",
                )
                if any(
                    getattr(old, field) != getattr(self, field) for field in protected
                ):
                    raise ValidationError("Finalized or void statements are immutable.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def calculated_total(self):
        return self.lines.aggregate(total=Sum("net_amount"))["total"] or Decimal("0.00")

    @property
    def variance(self):
        return (
            None
            if self.declared_total is None
            else self.declared_total - self.calculated_total
        )

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Royalty Statements cannot be deleted; void them instead."
        )


class RoyaltyAdvance(TimestampedModel):
    """Advance ledger per label, distributor, or other royalty supplier."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="royalty_advances")
    source_name = models.CharField(max_length=220)
    source_type = models.CharField(max_length=24, default="label")
    reference = models.CharField(max_length=120, blank=True)
    currency = models.CharField(max_length=3, validators=[CURRENCY])
    amount = models.DecimalField(max_digits=16, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    recouped_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0"))])
    received_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, max_length=2000)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="royalty_advances_created")

    class Meta:
        ordering = ("-received_on", "-created_at")

    def clean(self):
        self.currency = self.currency.upper()
        if self.recouped_amount > self.amount:
            raise ValidationError({"recouped_amount": "Recouped amount cannot exceed the advance."})

    @property
    def outstanding_amount(self):
        return self.amount - self.recouped_amount

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class RoyaltyStatementLine(TimestampedModel):
    class Basis(models.TextChoices):
        MASTER = "master", "Master"
        PUBLISHING = "publishing", "Publishing"
        MIXED = "mixed", "Mixed"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    statement = models.ForeignKey(
        RoyaltyStatement, on_delete=models.PROTECT, related_name="lines"
    )
    track = models.ForeignKey(
        "music.Track",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="royalty_lines",
    )
    release = models.ForeignKey(
        "music.Release",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="royalty_lines",
    )
    artist = models.ForeignKey(
        "artists.Artist",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="royalty_lines",
    )
    external_track_reference = models.CharField(max_length=180, blank=True)
    release_title = models.CharField(max_length=220, blank=True)
    upc_ean = models.CharField(max_length=14, blank=True)
    isrc = models.CharField(max_length=12, blank=True)
    territory_code = models.CharField(
        max_length=10, default="WORLDWIDE", validators=[TERRITORY]
    )
    platform = models.CharField(max_length=120, blank=True)
    usage_type = models.CharField(max_length=120, blank=True)
    rights_basis = models.CharField(max_length=16, choices=Basis.choices)
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    gross_amount = models.DecimalField(
        max_digits=16, decimal_places=2, validators=[MinValueValidator(0)]
    )
    deductions = models.DecimalField(
        max_digits=16, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    net_amount = models.DecimalField(max_digits=16, decimal_places=2, editable=False)
    description = models.CharField(max_length=500, blank=True)
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("sequence", "created_at")

    def clean(self):
        if self.statement.status != RoyaltyStatement.Status.DRAFT:
            raise ValidationError("Statement lines are editable only while draft.")
        for related in (self.track, self.release, self.artist):
            if related and related.organization_id != self.statement.organization_id:
                raise ValidationError(
                    "Statement line relationships must remain in one organization."
                )
        if self.deductions > self.gross_amount:
            raise ValidationError(
                {"deductions": "Deductions cannot exceed gross amount."}
            )

    def save(self, *args, **kwargs):
        current = RoyaltyStatement.objects.get(pk=self.statement_id)
        self.statement = current
        self.territory_code = self.territory_code.upper()
        self.net_amount = self.gross_amount - self.deductions
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if (
            RoyaltyStatement.objects.only("status").get(pk=self.statement_id).status
            != RoyaltyStatement.Status.DRAFT
        ):
            raise ValidationError("Finalized statement lines cannot be deleted.")
        return super().delete(*args, **kwargs)


class RoyaltyAllocation(models.Model):
    class Basis(models.TextChoices):
        MASTER = "master", "Master"
        PUBLISHING = "publishing", "Publishing"
        MANUAL = "manual", "Manual"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    statement_line = models.ForeignKey(
        RoyaltyStatementLine, on_delete=models.PROTECT, related_name="allocations"
    )
    party = models.ForeignKey(
        RightsParty, on_delete=models.PROTECT, related_name="royalty_allocations"
    )
    right_basis = models.CharField(max_length=16, choices=Basis.choices)
    percentage = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        validators=[MinValueValidator(PERCENT), MaxValueValidator(Decimal("100"))],
    )
    amount = models.DecimalField(
        max_digits=16, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="royalty_allocations_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("statement_line", "party", "right_basis"),
                name="rights_unique_line_party_basis",
            )
        ]

    def __str__(self):
        return f"{self.statement_line} / {self.party}"

    def clean(self):
        if self.statement_line.statement.status != RoyaltyStatement.Status.DRAFT:
            raise ValidationError("Allocations are editable only while draft.")
        if self.party.organization_id != self.statement_line.statement.organization_id:
            raise ValidationError(
                "Allocation party must belong to the statement organization."
            )
        if self.statement_line_id and self.amount and self.percentage:
            existing = (
                type(self)
                .objects.filter(statement_line_id=self.statement_line_id)
                .exclude(pk=self.pk)
            )
            totals = existing.aggregate(
                amount=Sum("amount"), percentage=Sum("percentage")
            )
            if (
                totals["amount"] or Decimal("0")
            ) + self.amount > self.statement_line.net_amount:
                raise ValidationError("Allocations cannot exceed the line net amount.")
            if (totals["percentage"] or Decimal("0")) + self.percentage > Decimal(
                "100"
            ):
                raise ValidationError("Allocation percentages cannot exceed 100%.")

    def save(self, *args, **kwargs):  # noqa: DJ012
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        status = RoyaltyStatement.objects.values_list("status", flat=True).get(
            lines__id=self.statement_line_id
        )
        if status != RoyaltyStatement.Status.DRAFT:
            raise ValidationError("Finalized allocations cannot be deleted.")
        return super().delete(*args, **kwargs)
