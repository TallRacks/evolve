from .models import Organization


def organizations_for_user(user):
    if not user or not user.is_authenticated or not user.is_active:
        return Organization.objects.none()
    if user.is_superuser:
        return Organization.objects.filter(is_active=True)
    return Organization.objects.filter(
        is_active=True, memberships__user=user, memberships__is_active=True
    ).distinct()
