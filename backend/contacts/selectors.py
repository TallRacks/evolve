from organizations.selectors import organizations_for_user

from .models import Contact


def contacts_for_user(user):
    if user and user.is_authenticated and user.is_active and user.is_superuser:
        return Contact.objects.select_related("organization").all()
    return Contact.objects.filter(
        organization_id__in=organizations_for_user(user).values("pk")
    ).select_related("organization")
