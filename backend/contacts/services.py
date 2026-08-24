from django.core.exceptions import PermissionDenied
from django.db import transaction

from audit.services import record_event
from organizations.permissions import user_has_organization_permission

from .models import Contact


def require_contact_permission(actor, organization, permission):
    if getattr(actor, "is_active", False) and getattr(actor, "is_superuser", False):
        return
    if not user_has_organization_permission(actor, organization, permission):
        raise PermissionDenied("You do not have permission to manage this contact.")


@transaction.atomic
def create_contact(*, actor, organization, data, request=None):
    require_contact_permission(actor, organization, "contact.manage")
    contact = Contact(organization=organization, **data)
    contact.full_clean()
    contact.save()
    record_event(
        actor=actor,
        organization=organization,
        action="contact.created",
        resource=contact,
        description="Created a business contact.",
        request=request,
    )
    return contact


@transaction.atomic
def update_contact(*, actor, contact, data, request=None):
    require_contact_permission(actor, contact.organization, "contact.manage")
    was_active = contact.is_active
    for field, value in data.items():
        setattr(contact, field, value)
    contact.full_clean()
    contact.save()
    action = "contact.deactivated" if was_active and not contact.is_active else "contact.updated"
    record_event(
        actor=actor,
        organization=contact.organization,
        action=action,
        resource=contact,
        description="Updated a business contact.",
        request=request,
    )
    return contact
