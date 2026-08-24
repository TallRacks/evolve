from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from audit.services import record_event
from organizations.permissions import user_has_organization_permission

from .models import Promoter, PromoterContact


def require_promoter_permission(actor, organization, permission):
    if getattr(actor, "is_active", False) and getattr(actor, "is_superuser", False):
        return
    if not user_has_organization_permission(actor, organization, permission):
        raise PermissionDenied("You do not have permission to manage this promoter.")


@transaction.atomic
def create_promoter(*, actor, organization, data, request=None):
    require_promoter_permission(actor, organization, "promoter.manage")
    promoter = Promoter(organization=organization, **data)
    promoter.full_clean()
    promoter.save()
    record_event(
        actor=actor,
        organization=organization,
        action="promoter.created",
        resource=promoter,
        description=f"Created promoter {promoter.name}.",
        request=request,
    )
    return promoter


@transaction.atomic
def update_promoter(*, actor, promoter, data, request=None):
    require_promoter_permission(actor, promoter.organization, "promoter.manage")
    previous = promoter.status
    for field, value in data.items():
        setattr(promoter, field, value)
    promoter.full_clean()
    promoter.save()
    action = "promoter.updated"
    if previous != promoter.status:
        action = (
            "promoter.reactivated"
            if promoter.status == Promoter.Status.ACTIVE
            else "promoter.deactivated"
        )
    record_event(
        actor=actor,
        organization=promoter.organization,
        action=action,
        resource=promoter,
        description=f"Updated promoter {promoter.name}.",
        request=request,
    )
    return promoter


@transaction.atomic
def add_promoter_contact(*, actor, promoter, contact, data, request=None):
    require_promoter_permission(actor, promoter.organization, "promoter.manage")
    link = (
        PromoterContact.objects.select_for_update()
        .filter(promoter=promoter, contact=contact)
        .first()
    )
    if link and link.is_active:
        raise ValidationError("This contact is already linked to the promoter.")
    if link:
        link.responsibility = data["responsibility"]
        link.is_primary = data.get("is_primary", False)
        link.is_active = True
    else:
        link = PromoterContact(promoter=promoter, contact=contact, **data)
    link.full_clean()
    link.save()
    record_event(
        actor=actor,
        organization=promoter.organization,
        action="promoter.contact_added",
        resource=promoter,
        description=f"Added a contact relationship to {promoter.name}.",
        request=request,
    )
    return link


@transaction.atomic
def update_promoter_contact(*, actor, link, data, request=None):
    require_promoter_permission(actor, link.promoter.organization, "promoter.manage")
    was_active = link.is_active
    for field, value in data.items():
        setattr(link, field, value)
    link.full_clean()
    link.save()
    action = (
        "promoter.contact_removed"
        if was_active and not link.is_active
        else "promoter.contact_updated"
    )
    record_event(
        actor=actor,
        organization=link.promoter.organization,
        action=action,
        resource=link.promoter,
        description=f"Updated a contact relationship for {link.promoter.name}.",
        request=request,
    )
    return link
