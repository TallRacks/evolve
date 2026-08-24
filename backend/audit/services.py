from .models import AuditEvent


def request_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",", 1)[0].strip() or request.META.get("REMOTE_ADDR")


def record_event(*, actor, action, resource, description, organization=None, request=None):
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        organization=organization,
        action=action,
        resource_type=resource.__class__.__name__,
        resource_id=str(resource.pk),
        description=description,
        ip_address=request_ip(request),
    )
