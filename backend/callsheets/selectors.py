from .models import CallSheet, CallSheetVersion


def call_sheets_for_user(user):
    queryset = CallSheet.objects.select_related("organization", "booking", "booking__artist")
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return queryset.none()
    if user.is_superuser:
        return queryset
    return queryset.filter(
        organization__memberships__user=user,
        organization__memberships__is_active=True,
        organization__is_active=True,
    ).distinct()


def versions_for_user(user):
    return CallSheetVersion.objects.filter(
        call_sheet_id__in=call_sheets_for_user(user).values("pk")
    ).select_related("call_sheet__organization", "call_sheet__booking", "published_by")
