from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from audit.services import record_event
from notifications.services import create_notification
from organizations.models import Membership
from organizations.permissions import user_has_organization_permission

from .models import (
    MasterRight,
    PublishingRight,
    RightsParty,
    RoyaltyAllocation,
    RoyaltySource,
    RoyaltyStatement,
    RoyaltyStatementLine,
    TrackWork,
    Work,
    WorkContributor,
)


def require(actor, organization, permission):
    if not user_has_organization_permission(actor, organization, permission):
        raise PermissionDenied(
            "You do not have permission to access Rights and Royalties."
        )


def emit(actor, organization, action, resource, description, request=None):
    return record_event(
        actor=actor,
        organization=organization,
        action=action,
        resource=resource,
        description=description,
        request=request,
    )


def rights_users(organization):
    return [
        m.user
        for m in Membership.objects.active()
        .filter(
            organization=organization,
            role__in=(Membership.Role.OWNER, Membership.Role.ADMIN),
        )
        .select_related("user")
    ]


def periods_overlap(a_start, a_end, b_start, b_end):
    return (not a_end or not b_start or a_end >= b_start) and (
        not b_end or not a_start or b_end >= a_start
    )


def territories_overlap(a, b):
    return a == b or "WORLDWIDE" in (a, b)


@transaction.atomic
def create_work(*, actor, organization, data, request=None):
    require(actor, organization, "rights.manage")
    work = Work(organization=organization, created_by=actor, **data)
    work.save()
    emit(
        actor,
        organization,
        "rights.work_created",
        work,
        f"Created Work {work.id}.",
        request,
    )
    return work


@transaction.atomic
def archive_work(*, actor, work, request=None):
    require(actor, work.organization, "rights.manage")
    locked = Work.objects.select_for_update().get(pk=work.pk)
    if locked.status == Work.Status.ARCHIVED:
        raise ValidationError("Work is already archived.")
    Work.objects.filter(pk=locked.pk).update(
        status=Work.Status.ARCHIVED,
        archived_at=timezone.now(),
        updated_at=timezone.now(),
    )
    locked.refresh_from_db()
    emit(
        actor,
        locked.organization,
        "rights.work_archived",
        locked,
        f"Archived Work {locked.id}.",
        request,
    )
    return locked


@transaction.atomic
def create_party(*, actor, organization, data, request=None):
    require(actor, organization, "rights.manage")
    party = RightsParty(organization=organization, **data)
    party.save()
    emit(
        actor,
        organization,
        "rights.party_created",
        party,
        f"Created Rights Party {party.id}.",
        request,
    )
    return party


@transaction.atomic
def link_track(*, actor, work, track, relationship_type, request=None):
    require(actor, work.organization, "rights.manage")
    link = TrackWork(work=work, track=track, relationship_type=relationship_type)
    link.save()
    emit(
        actor,
        work.organization,
        "rights.track_linked",
        work,
        f"Linked Track {track.id} to Work {work.id}.",
        request,
    )
    return link


@transaction.atomic
def add_contributor(*, actor, work, data, request=None):
    require(actor, work.organization, "rights.manage")
    contributor = WorkContributor(work=work, **data)
    contributor.save()
    emit(
        actor,
        work.organization,
        "rights.contributor_added",
        work,
        f"Added contributor to Work {work.id}.",
        request,
    )
    return contributor


def applicable(queryset, effective_from, effective_to, territory):
    return [
        row
        for row in queryset
        if territories_overlap(row.territory_code, territory)
        and periods_overlap(
            row.effective_from, row.effective_to, effective_from, effective_to
        )
    ]


@transaction.atomic
def add_master_right(*, actor, track, data, request=None):
    require(actor, track.organization, "rights.manage")
    type(track).objects.select_for_update().get(pk=track.pk)
    candidate = MasterRight(organization=track.organization, track=track, **data)
    candidate.full_clean()
    rows = applicable(
        MasterRight.objects.filter(track=track).select_for_update(),
        candidate.effective_from,
        candidate.effective_to,
        candidate.territory_code,
    )
    if (
        sum((row.ownership_percentage for row in rows), Decimal("0"))
        + candidate.ownership_percentage
        > 100
    ):
        raise ValidationError("Applicable Master ownership cannot exceed 100%.")
    candidate.save()
    emit(
        actor,
        track.organization,
        "rights.master_added",
        candidate,
        f"Added Master Right {candidate.id}.",
        request,
    )
    return candidate


@transaction.atomic
def add_publishing_right(*, actor, work, data, request=None):
    require(actor, work.organization, "rights.manage")
    Work.objects.select_for_update().get(pk=work.pk)
    candidate = PublishingRight(organization=work.organization, work=work, **data)
    candidate.full_clean()
    rows = applicable(
        PublishingRight.objects.filter(work=work).select_for_update(),
        candidate.effective_from,
        candidate.effective_to,
        candidate.territory_code,
    )
    if (
        sum((row.ownership_percentage for row in rows), Decimal("0"))
        + candidate.ownership_percentage
        > 100
    ):
        raise ValidationError("Applicable Publishing ownership cannot exceed 100%.")
    candidate.save()
    emit(
        actor,
        work.organization,
        "rights.publishing_added",
        candidate,
        f"Added Publishing Right {candidate.id}.",
        request,
    )
    return candidate


@transaction.atomic
def create_statement(*, actor, organization, data, request=None):
    require(actor, organization, "royalties.manage")
    if not data.get("source") and data.get("source_name"):
        data = {
            **data,
            "source": RoyaltySource.objects.filter(
                organization=organization,
                name__iexact=data["source_name"].strip(),
                is_active=True,
            ).first(),
        }
    statement = RoyaltyStatement(organization=organization, created_by=actor, **data)
    statement.save()
    emit(
        actor,
        organization,
        "royalties.statement_created",
        statement,
        f"Created Royalty Statement {statement.statement_reference}.",
        request,
    )
    return statement


@transaction.atomic
def update_statement(*, actor, statement, data, request=None):
    require(actor, statement.organization, "royalties.manage")
    locked = RoyaltyStatement.objects.select_for_update().get(pk=statement.pk)
    if locked.status != RoyaltyStatement.Status.DRAFT:
        raise ValidationError("Only draft statements can be edited.")
    for field, value in data.items():
        setattr(locked, field, value)
    locked.save()
    emit(
        actor,
        locked.organization,
        "royalties.statement_updated",
        locked,
        f"Updated Royalty Statement {locked.statement_reference}.",
        request,
    )
    return locked


@transaction.atomic
def add_statement_line(*, actor, statement, data, request=None):
    require(actor, statement.organization, "royalties.manage")
    locked = RoyaltyStatement.objects.select_for_update().get(pk=statement.pk)
    line = RoyaltyStatementLine(statement=locked, **data)
    line.save()
    emit(
        actor,
        locked.organization,
        "royalties.line_added",
        line,
        f"Added line to Royalty Statement {locked.statement_reference}.",
        request,
    )
    return line


@transaction.atomic
def allocate_manual(*, actor, line, party, percentage, amount, request=None):
    require(actor, line.statement.organization, "royalties.manage")
    locked = (
        RoyaltyStatementLine.objects.select_for_update()
        .select_related("statement")
        .get(pk=line.pk)
    )
    if locked.statement.status != RoyaltyStatement.Status.DRAFT:
        raise ValidationError("Allocations are editable only while draft.")
    amount = Decimal(amount)
    current = locked.allocations.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    current_percentage = locked.allocations.aggregate(total=Sum("percentage"))[
        "total"
    ] or Decimal("0")
    percentage = Decimal(percentage)
    if (
        amount <= 0
        or current + amount > locked.net_amount
        or current_percentage + percentage > Decimal("100")
    ):
        raise ValidationError("Allocation exceeds the line net amount.")
    allocation = RoyaltyAllocation(
        statement_line=locked,
        party=party,
        right_basis=RoyaltyAllocation.Basis.MANUAL,
        percentage=percentage,
        amount=amount,
        created_by=actor,
    )
    allocation.save()
    emit(
        actor,
        locked.statement.organization,
        "royalties.allocation_added",
        allocation,
        f"Added allocation to statement line {locked.id}.",
        request,
    )
    return allocation


@transaction.atomic
def update_manual_allocation(
    *, actor, allocation, party, percentage, amount, request=None
):
    require(actor, allocation.statement_line.statement.organization, "royalties.manage")
    locked = RoyaltyAllocation.objects.select_for_update().get(pk=allocation.pk)
    if locked.right_basis != RoyaltyAllocation.Basis.MANUAL:
        raise ValidationError("Generated allocations cannot be edited.")
    locked.party = party
    locked.percentage = Decimal(percentage)
    locked.amount = Decimal(amount)
    locked.save()
    emit(
        actor,
        locked.statement_line.statement.organization,
        "royalties.allocation_updated",
        locked,
        f"Updated allocation {locked.id}.",
        request,
    )
    return locked


@transaction.atomic
def generate_allocations(*, actor, line, request=None):
    require(actor, line.statement.organization, "royalties.manage")
    locked = RoyaltyStatementLine.objects.select_for_update().get(pk=line.pk)
    if (
        locked.statement.status != RoyaltyStatement.Status.DRAFT
        or locked.allocations.exists()
    ):
        raise ValidationError(
            "Automatic allocation requires an unallocated draft line."
        )
    on_date = locked.statement.period_end
    if locked.rights_basis == RoyaltyStatementLine.Basis.MASTER and locked.track_id:
        rights = MasterRight.objects.filter(track=locked.track).select_for_update()
        basis = RoyaltyAllocation.Basis.MASTER
    elif (
        locked.rights_basis == RoyaltyStatementLine.Basis.PUBLISHING and locked.track_id
    ):
        work_ids = TrackWork.objects.filter(track=locked.track).values_list(
            "work_id", flat=True
        )
        rights = PublishingRight.objects.filter(
            work_id__in=work_ids
        ).select_for_update()
        basis = RoyaltyAllocation.Basis.PUBLISHING
    else:
        raise ValidationError(
            "Automatic allocation requires an explicit Master or Publishing "
            "basis and resolved Track."
        )
    rights = [
        r
        for r in rights
        if territories_overlap(r.territory_code, locked.territory_code)
        and (not r.effective_from or r.effective_from <= on_date)
        and (not r.effective_to or r.effective_to >= on_date)
    ]
    if not rights:
        raise ValidationError("No applicable rights records were found.")
    total_percentage = sum(
        (right.ownership_percentage for right in rights), Decimal("0")
    )
    if total_percentage > Decimal("100"):
        raise ValidationError("Applicable rights exceed 100%.")
    created = []
    for index, right in enumerate(rights):
        amount = (
            locked.net_amount * right.ownership_percentage / Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if index == len(rights) - 1 and total_percentage == Decimal("100"):
            amount = locked.net_amount - sum(
                (allocation.amount for allocation in created), Decimal("0")
            )
        if amount > 0:
            created.append(
                RoyaltyAllocation.objects.create(
                    statement_line=locked,
                    party=right.party,
                    right_basis=basis,
                    percentage=right.ownership_percentage,
                    amount=amount,
                    created_by=actor,
                )
            )
    if sum((a.amount for a in created), Decimal("0")) > locked.net_amount:
        raise ValidationError("Generated allocations exceed line net amount.")
    emit(
        actor,
        locked.statement.organization,
        "royalties.allocations_generated",
        locked,
        f"Generated allocations for statement line {locked.id}.",
        request,
    )
    return created


@transaction.atomic
def finalize_statement(*, actor, statement, request=None):
    require(actor, statement.organization, "royalties.statement.finalize")
    locked = RoyaltyStatement.objects.select_for_update().get(pk=statement.pk)
    if locked.status != RoyaltyStatement.Status.DRAFT or not locked.lines.exists():
        raise ValidationError("Only a draft statement with lines can be finalized.")
    for line in locked.lines.select_for_update():
        if (
            line.rights_basis
            in (
                RoyaltyStatementLine.Basis.MASTER,
                RoyaltyStatementLine.Basis.PUBLISHING,
            )
            and not line.track_id
        ):
            raise ValidationError(
                "Master and Publishing lines require a resolved Track."
            )
        allocated = line.allocations.aggregate(total=Sum("amount"))["total"] or Decimal(
            "0"
        )
        if allocated != line.net_amount:
            raise ValidationError(
                "Every statement line must be fully allocated before finalization."
            )
    if locked.declared_total is not None and locked.variance != Decimal("0.00"):
        raise ValidationError(
            "Declared and calculated statement totals must reconcile."
        )
    now = timezone.now()
    RoyaltyStatement.objects.filter(pk=locked.pk).update(
        status=RoyaltyStatement.Status.FINALIZED,
        finalized_by=actor,
        finalized_at=now,
        updated_at=now,
    )
    locked.refresh_from_db()
    emit(
        actor,
        locked.organization,
        "royalties.statement_finalized",
        locked,
        f"Finalized Royalty Statement {locked.statement_reference}.",
        request,
    )
    create_notification(
        organization=locked.organization,
        notification_type="royalty.statement_finalized",
        category="rights",
        title="Royalty statement finalized",
        message=f"Royalty statement {locked.statement_reference} was finalized.",
        users=rights_users(locked.organization),
        actor=actor,
        source=locked,
        action_url=f"/workspace/royalties/statements/{locked.pk}",
    )
    return locked


@transaction.atomic
def void_statement(*, actor, statement, reason, request=None):
    require(actor, statement.organization, "royalties.manage")
    reason = reason.strip()
    if not reason:
        raise ValidationError("A void reason is required.")
    locked = RoyaltyStatement.objects.select_for_update().get(pk=statement.pk)
    if locked.status != RoyaltyStatement.Status.FINALIZED:
        raise ValidationError("Only finalized statements can be voided.")
    now = timezone.now()
    RoyaltyStatement.objects.filter(pk=locked.pk).update(
        status=RoyaltyStatement.Status.VOID,
        voided_by=actor,
        voided_at=now,
        void_reason=reason,
        updated_at=now,
    )
    locked.refresh_from_db()
    emit(
        actor,
        locked.organization,
        "royalties.statement_voided",
        locked,
        f"Voided Royalty Statement {locked.statement_reference}; reason recorded.",
        request,
    )
    return locked
