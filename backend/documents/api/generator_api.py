from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking
from documents.generator_services import generate_booking_office, generate_release_office
from documents.selectors import documents_for_user
from music.models import Release
from organizations.selectors import organizations_for_user


class OfficeRefreshView(APIView):
    def post(self, request, document_id):
        organization = get_object_or_404(
            organizations_for_user(request.user),
            pk=request.data.get("organization_id") or request.query_params.get("organization_id"),
        )
        document = get_object_or_404(
            documents_for_user(request.user, organization).filter(
                pk=document_id, office_content__isnull=False
            )
        )
        marker = "[evolve-generator:"
        if not document.description.startswith(marker):
            raise ValidationError("This Office document is not source-generated.")
        key = document.description.split(marker, 1)[1].split("]", 1)[0]
        if not request.data.get("confirm"):
            return Response(
                {
                    "requires_confirmation": True,
                    "generator": key,
                    "revision_number": document.office_content.revision_number,
                    "message": (
                        "Refresh creates a new revision and replaces the current generated content."
                    ),
                },
                status=409,
            )
        try:
            link = document.links.filter(booking__isnull=False).select_related("booking").first()
            if link and link.booking_id:
                refreshed, _ = generate_booking_office(
                    actor=request.user,
                    booking=link.booking,
                    generator=key,
                    request=request,
                    refresh_document=document,
                )
            elif link and link.release_id:
                refreshed, _ = generate_release_office(
                    actor=request.user,
                    release=link.release,
                    generator=key,
                    request=request,
                    refresh_document=document,
                )
            else:
                link = (
                    document.links.filter(release__isnull=False).select_related("release").first()
                )
                if not link:
                    raise ValidationError("The generated source record is unavailable.")
                refreshed, _ = generate_release_office(
                    actor=request.user,
                    release=link.release,
                    generator=key,
                    request=request,
                    refresh_document=document,
                )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            {
                "document": str(refreshed.pk),
                "revision_number": refreshed.office_content.revision_number,
                "refreshed": True,
            }
        )


class BookingOfficeGeneratorView(APIView):
    def post(self, request, booking_id, generator):
        booking = get_object_or_404(
            Booking.objects.select_related("organization", "artist"),
            pk=booking_id,
            organization__in=organizations_for_user(request.user),
        )
        try:
            document, reused = generate_booking_office(
                actor=request.user, booking=booking, generator=generator, request=request
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"document": str(document.pk), "title": document.title, "reused": reused})


class ReleaseOfficeGeneratorView(APIView):
    def post(self, request, release_id, generator):
        release = get_object_or_404(
            Release.objects.select_related("organization", "primary_artist"),
            pk=release_id,
            organization__in=organizations_for_user(request.user),
        )
        try:
            document, reused = generate_release_office(
                actor=request.user, release=release, generator=generator, request=request
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"document": str(document.pk), "title": document.title, "reused": reused})
