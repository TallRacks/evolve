from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from audit.services import record_event
from notifications.models import Notification
from notifications.services import create_notification
from organizations.permissions import user_has_organization_permission

from .models import (
    Contract,
    ContractApproval,
    ContractDocument,
    ContractParty,
    ContractSection,
    ContractTerm,
)

TRANSITIONS = {
    "draft": {"in_review", "cancelled"},
    "in_review": {"draft", "approved", "cancelled"},
    "approved": {"sent", "draft"},
    "sent": {"partially_signed", "executed", "cancelled"},
    "partially_signed": {"executed", "cancelled"},
    "executed": {"terminated", "archived"},
    "cancelled": {"archived"},
    "terminated": {"archived"},
    "archived": set(),
}


def require(actor, organization, permission):
    if not user_has_organization_permission(actor, organization, permission):
        raise PermissionDenied(
            "You do not have permission to manage Contracts for this organization."
        )


def audit(actor, row, action, description, request=None):
    record_event(
        actor=actor,
        organization=row.contract.organization if hasattr(row, "contract") else row.organization,
        action=action,
        resource=row,
        description=description,
        request=request,
    )


def notify(row, actor, notification_type, title, users, request=None):
    create_notification(
        organization=row.organization,
        notification_type=notification_type,
        category=Notification.Category.CONTRACTS,
        title=title,
        message=f"{row.reference} requires attention.",
        users=users,
        actor=actor,
        source=row,
        action_url=f"/workspace/contracts/{row.id}",
    )


def create_contract(*, actor, organization, data, request=None):
    require(actor, organization, "contract.manage")
    data.pop("status", None)
    row = Contract(organization=organization, created_by=actor, **data)
    row.save()
    audit(actor, row, "contract.created", "Contract created.", request)
    return row


@transaction.atomic
def create_from_booking(*, actor, booking, request=None):
    require(actor, booking.organization, "contract.manage")
    row = create_contract(
        actor=actor,
        organization=booking.organization,
        data={
            "title": f"{booking.title} - {booking.reference} performance agreement",
            "contract_type": Contract.Type.PERFORMANCE,
            "booking": booking,
            "artist": booking.artist,
            "promoter": booking.promoter,
            "effective_date": booking.event_date,
            "currency": booking.currency or "",
        },
        request=request,
    )
    if booking.performance_fee is not None and user_has_organization_permission(
        actor, booking.organization, "booking.commercial.view"
    ):
        ContractTerm.objects.create(
            contract=row,
            term_type=ContractTerm.Type.FEE,
            title="Performance fee",
            value_decimal=booking.performance_fee,
            currency=booking.currency,
            sequence=1,
        )
        audit(
            actor,
            row.terms.first(),
            "contract.term_added",
            "Contract term added from Booking.",
            request,
        )
    return row


def update_contract(row, *, actor, data, request=None):
    require(actor, row.organization, "contract.manage")
    for key in (
        "organization",
        "status",
        "reference",
        "created_by",
        "archived_at",
        "terminated_at",
        "termination_reason",
    ):
        data.pop(key, None)
    changed = [key for key, value in data.items() if getattr(row, key) != value]
    for key, value in data.items():
        setattr(row, key, value)
    row.save()
    audit(
        actor,
        row,
        "contract.updated",
        f"Contract fields updated: {', '.join(changed) or 'none'}.",
        request,
    )
    return row


def execution_errors(row):
    errors = []
    if not row.parties.exists():
        errors.append("At least one party is required.")
    if not row.terms.exists():
        errors.append("At least one term is required.")
    if row.approvals.filter(status=ContractApproval.Status.PENDING).exists():
        errors.append("All requested approvals must be decided.")
    if row.approvals.filter(status=ContractApproval.Status.REJECTED).exists():
        errors.append("Rejected approvals must be resolved.")
    if (
        row.parties.filter(is_signatory=True)
        .exclude(signing_status=ContractParty.SigningStatus.SIGNED)
        .exists()
    ):
        errors.append("Every required signatory must be marked signed.")
    return errors


@transaction.atomic
def transition_contract(row, *, actor, to_status, reason="", request=None):
    require(actor, row.organization, "contract.status.manage")
    locked = Contract.objects.select_for_update().get(pk=row.pk)
    if to_status not in TRANSITIONS.get(locked.status, set()):
        raise ValidationError({"to_status": "This Contract transition is not allowed."})
    if to_status == Contract.Status.APPROVED:
        if (
            locked.approvals.filter(status=ContractApproval.Status.PENDING).exists()
            or locked.approvals.filter(status=ContractApproval.Status.REJECTED).exists()
        ):
            raise ValidationError("All requested approvals must be approved.")
    if to_status == Contract.Status.EXECUTED:
        errors = execution_errors(locked)
        if errors:
            raise ValidationError({"to_status": errors})
    if to_status == Contract.Status.TERMINATED and not reason.strip():
        raise ValidationError({"reason": "A termination reason is required."})
    now = timezone.now()
    Contract.objects.filter(pk=locked.pk).update(
        status=to_status,
        archived_at=now if to_status == Contract.Status.ARCHIVED else locked.archived_at,
        terminated_at=now if to_status == Contract.Status.TERMINATED else locked.terminated_at,
        termination_reason=reason.strip()
        if to_status == Contract.Status.TERMINATED
        else locked.termination_reason,
        signed_date=timezone.localdate()
        if to_status == Contract.Status.EXECUTED and not locked.signed_date
        else locked.signed_date,
        updated_at=now,
    )
    locked.refresh_from_db()
    action = (
        "contract.terminated"
        if to_status == "terminated"
        else "contract.archived"
        if to_status == "archived"
        else "contract.status_changed"
    )
    audit(actor, locked, action, f"Contract status changed to {to_status}.", request)
    return locked


def snapshot_values(data):
    source = (
        data.get("linked_artist")
        or data.get("linked_promoter")
        or data.get("linked_contact")
        or data.get("linked_rights_party")
    )
    if source and not data.get("display_name"):
        data["display_name"] = (
            getattr(source, "stage_name", None)
            or getattr(source, "name", None)
            or getattr(source, "full_name", None)
            or getattr(source, "display_name", "")
        )
    if source and not data.get("email_snapshot"):
        data["email_snapshot"] = getattr(source, "email", "")
    return data


CHILDREN = {
    "party": (ContractParty, "contract.party"),
    "term": (ContractTerm, "contract.term"),
    "section": (ContractSection, "contract.section"),
}


@transaction.atomic
def create_child(kind, contract, *, actor, data, request=None):
    require(actor, contract.organization, "contract.manage")
    Contract.objects.select_for_update().get(pk=contract.pk)
    if contract.status not in {"draft", "in_review"}:
        raise ValidationError("Contract content is no longer editable.")
    model, action = CHILDREN[kind]
    if kind == "party":
        data = snapshot_values(data)
    if kind in {"term", "section"} and not data.get("sequence"):
        data["sequence"] = (
            model.objects.filter(contract=contract).aggregate(value=Max("sequence"))["value"] or 0
        ) + 1
    row = model(contract=contract, **data)
    row.save()
    audit(actor, row, f"{action}_added", f"Contract {kind} added.", request)
    return row


def update_child(kind, row, *, actor, data, request=None):
    require(actor, row.contract.organization, "contract.manage")
    for key in ("contract", "signing_status", "signed_at", "signing_note"):
        data.pop(key, None)
    if kind == "party":
        data = snapshot_values(data)
    for key, value in data.items():
        setattr(row, key, value)
    row.save()
    audit(actor, row, f"contract.{kind}_updated", f"Contract {kind} updated.", request)
    return row


def remove_child(kind, row, *, actor, request=None):
    require(actor, row.contract.organization, "contract.manage")
    audit(actor, row, f"contract.{kind}_removed", f"Contract {kind} removed.", request)
    row.delete()


@transaction.atomic
def set_signing_status(row, *, actor, status, note="", request=None):
    require(actor, row.contract.organization, "contract.signature.manage")
    locked = (
        ContractParty.objects.select_for_update()
        .select_related("contract__organization")
        .get(pk=row.pk)
    )
    if locked.contract.status not in {"sent", "partially_signed"}:
        raise ValidationError("Signing state is recorded only after a Contract is sent.")
    if not locked.is_signatory:
        raise ValidationError("Only required signatories have a signing state.")
    if status not in {"pending", "signed", "declined"}:
        raise ValidationError({"status": "Invalid signing state."})
    ContractParty.objects.filter(pk=locked.pk).update(
        signing_status=status,
        signed_at=timezone.now() if status == "signed" else None,
        signing_note=note[:500],
        updated_at=timezone.now(),
    )
    if status == "signed" and locked.contract.status == "sent":
        Contract.objects.filter(pk=locked.contract_id).update(
            status="partially_signed", updated_at=timezone.now()
        )
        locked.contract.refresh_from_db()
        audit(
            actor,
            locked.contract,
            "contract.status_changed",
            "Contract status changed to partially_signed.",
            request,
        )
    locked.refresh_from_db()
    audit(
        actor,
        locked,
        "contract.party_signing_status_changed",
        "Contract party signing status changed.",
        request,
    )
    return locked


@transaction.atomic
def request_approval(contract, *, actor, membership, request=None):
    require(actor, contract.organization, "contract.manage")
    if contract.status != "in_review":
        raise ValidationError("Approvals may be requested only while In review.")
    if not user_has_organization_permission(
        membership.user, contract.organization, "contract.approve"
    ):
        raise ValidationError({"membership": "Selected member cannot approve Contracts."})
    sequence = (contract.approvals.aggregate(value=Max("sequence"))["value"] or 0) + 1
    row = ContractApproval(contract=contract, membership=membership, sequence=sequence)
    row.save()
    audit(actor, row, "contract.approval_requested", "Contract approval requested.", request)
    notify(
        contract,
        actor,
        "contract.approval_requested",
        "Contract approval requested",
        [membership.user],
    )
    return row


@transaction.atomic
def decide_approval(row, *, actor, decision, comment="", request=None):
    locked = (
        ContractApproval.objects.select_for_update()
        .select_related("contract__organization", "membership__user")
        .get(pk=row.pk)
    )
    if actor.pk != locked.membership.user_id and not actor.is_superuser:
        raise PermissionDenied("Only the assigned approver may decide this request.")
    require(actor, locked.contract.organization, "contract.approve")
    if locked.status != "pending" or decision not in {"approved", "rejected", "cancelled"}:
        raise ValidationError("This approval cannot be decided.")
    ContractApproval.objects.filter(pk=locked.pk).update(
        status=decision,
        comment=comment,
        decided_at=timezone.now(),
        decided_by=actor,
        updated_at=timezone.now(),
    )
    locked.refresh_from_db()
    audit(actor, locked, f"contract.approval_{decision}", f"Contract approval {decision}.", request)
    return locked


def link_document(contract, *, actor, document, request=None):
    require(actor, contract.organization, "contract.manage")
    row = ContractDocument(contract=contract, document=document)
    row.save()
    audit(actor, row, "contract.document_linked", "Document linked to Contract.", request)
    return row


def unlink_document(row, *, actor, request=None):
    require(actor, row.contract.organization, "contract.manage")
    audit(actor, row, "contract.document_unlinked", "Document unlinked from Contract.", request)
    row.delete()
