from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking
from documents.generator_services import generate_booking_office, generate_release_office
from music.models import Release
from organizations.selectors import organizations_for_user


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
