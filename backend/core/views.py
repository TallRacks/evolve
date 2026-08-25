import uuid

from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .consolidation import dashboard, global_search


def organization_id(request):
    value = request.query_params.get("organization_id")
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError as error:
        raise ValidationError({"organization_id": "Use a valid UUID."}) from error


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok", "service": "evolve-api"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search(request):
    query = request.query_params.get("q", "").strip()
    if len(query) < 2:
        raise ValidationError({"q": "Enter at least 2 characters."})
    if len(query) > 100:
        raise ValidationError({"q": "Search is limited to 100 characters."})
    groups = global_search(
        request.user, query, organization_id(request)
    )
    return Response({"query": query, "groups": groups})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_view(request):
    return Response(dashboard(request.user, organization_id(request)))
