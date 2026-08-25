from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking
from finance.models import Invoice, InvoiceLineItem, Payment
from finance.selectors import invoices_for_user, overview, payments_for_user
from finance.services import (
    add_line_item,
    allocate_payment,
    create_invoice,
    create_invoice_from_booking,
    issue_invoice,
    record_payment,
    remove_line_item,
    require,
    update_invoice,
    update_line_item,
    void_invoice,
    void_payment,
)
from organizations.api.permissions import PlatformSuperuser
from organizations.models import Organization
from organizations.selectors import organizations_for_user
from white_label.services import authenticate_api_key

from .serializers import (
    AllocateSerializer,
    DeveloperInvoiceSerializer,
    DeveloperPaymentSerializer,
    InvoiceCreateSerializer,
    InvoiceSerializer,
    InvoiceUpdateSerializer,
    LineItemSerializer,
    PaymentCreateSerializer,
    PaymentSerializer,
    ReasonSerializer,
)


def validation(call):
    try:
        return call()
    except DjangoValidationError as error:
        raise ValidationError(
            error.message_dict if hasattr(error, "message_dict") else error.messages
        ) from error


def organization_for(user, organization_id, permission="finance.view"):
    organization = get_object_or_404(
        Organization.objects.filter(pk__in=organizations_for_user(user)), pk=organization_id
    )
    require(user, organization, permission)
    return organization


def invoice_for(user, pk):
    return get_object_or_404(
        invoices_for_user(user)
        .select_related("organization", "booking", "booking__artist")
        .prefetch_related("line_items", "allocations__payment"),
        pk=pk,
    )


def payment_for(user, pk):
    return get_object_or_404(
        payments_for_user(user)
        .select_related("organization")
        .prefetch_related("allocations__invoice"),
        pk=pk,
    )


class InvoiceListCreateView(APIView):
    def get(self, request):
        qs = (
            invoices_for_user(request.user)
            .select_related("organization", "booking", "booking__artist")
            .prefetch_related("line_items", "allocations__payment")
        )
        if request.query_params.get("organization_id"):
            organization = organization_for(request.user, request.query_params["organization_id"])
            qs = qs.filter(organization=organization)
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(invoice_number__icontains=search)
                | Q(booking__reference__icontains=search)
                | Q(artist_name_snapshot__icontains=search)
                | Q(billed_to_name__icontains=search)
            )
        for parameter, field in (
            ("status", "status"),
            ("currency", "currency"),
            ("artist", "booking__artist_id"),
            ("booking", "booking_id"),
        ):
            if request.query_params.get(parameter):
                qs = qs.filter(**{field: request.query_params[parameter]})
        if request.query_params.get("overdue") == "true":
            qs = qs.filter(
                status=Invoice.Status.ISSUED,
                due_date__lt=timezone.localdate(),
            )
        return Response(InvoiceSerializer(qs[:250], many=True).data)

    def post(self, request):
        serializer = InvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        organization = organization_for(
            request.user, values.pop("organization_id"), "finance.manage"
        )
        booking_id = values.pop("booking_id", None)
        if booking_id:
            values["booking"] = get_object_or_404(Booking, pk=booking_id, organization=organization)
        return Response(
            InvoiceSerializer(
                validation(
                    lambda: create_invoice(
                        actor=request.user, organization=organization, data=values, request=request
                    )
                )
            ).data,
            status=201,
        )


class InvoiceDetailView(APIView):
    def get(self, request, pk):
        return Response(InvoiceSerializer(invoice_for(request.user, pk)).data)

    def patch(self, request, pk):
        invoice = invoice_for(request.user, pk)
        serializer = InvoiceUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(
            InvoiceSerializer(
                validation(
                    lambda: update_invoice(
                        actor=request.user,
                        invoice=invoice,
                        data=serializer.validated_data,
                        request=request,
                    )
                )
            ).data
        )


class InvoiceIssueView(APIView):
    def post(self, request, pk):
        return Response(
            InvoiceSerializer(
                validation(
                    lambda: issue_invoice(
                        actor=request.user, invoice=invoice_for(request.user, pk), request=request
                    )
                )
            ).data
        )


class InvoiceVoidView(APIView):
    def post(self, request, pk):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            InvoiceSerializer(
                validation(
                    lambda: void_invoice(
                        actor=request.user,
                        invoice=invoice_for(request.user, pk),
                        reason=serializer.validated_data["reason"],
                        request=request,
                    )
                )
            ).data
        )


class LineItemView(APIView):
    def post(self, request, pk):
        invoice = invoice_for(request.user, pk)
        serializer = LineItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            LineItemSerializer(
                validation(
                    lambda: add_line_item(
                        actor=request.user,
                        invoice=invoice,
                        data=serializer.validated_data,
                        request=request,
                    )
                )
            ).data,
            status=201,
        )


class LineItemDetailView(APIView):
    def patch(self, request, pk, item_id):
        invoice = invoice_for(request.user, pk)
        item = get_object_or_404(InvoiceLineItem, pk=item_id, invoice=invoice)
        serializer = LineItemSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(
            LineItemSerializer(
                validation(
                    lambda: update_line_item(
                        actor=request.user,
                        item=item,
                        data=serializer.validated_data,
                        request=request,
                    )
                )
            ).data
        )

    def delete(self, request, pk, item_id):
        invoice = invoice_for(request.user, pk)
        item = get_object_or_404(InvoiceLineItem, pk=item_id, invoice=invoice)
        validation(lambda: remove_line_item(actor=request.user, item=item, request=request))
        return Response(status=204)


class BookingInvoiceView(APIView):
    def post(self, request, booking_id):
        booking = get_object_or_404(
            Booking.objects.select_related("organization", "artist"), pk=booking_id
        )
        return Response(
            InvoiceSerializer(
                validation(
                    lambda: create_invoice_from_booking(
                        actor=request.user, booking=booking, request=request
                    )
                )
            ).data,
            status=201,
        )


class PaymentListCreateView(APIView):
    def get(self, request):
        qs = (
            payments_for_user(request.user)
            .select_related("organization")
            .prefetch_related("allocations__invoice")
        )
        if request.query_params.get("organization_id"):
            organization = organization_for(request.user, request.query_params["organization_id"])
            qs = qs.filter(organization=organization)
        return Response(PaymentSerializer(qs[:250], many=True).data)

    def post(self, request):
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        organization = organization_for(
            request.user, values.pop("organization_id"), "finance.payment.record"
        )
        return Response(
            PaymentSerializer(
                validation(
                    lambda: record_payment(
                        actor=request.user, organization=organization, data=values, request=request
                    )
                )
            ).data,
            status=201,
        )


class PaymentDetailView(APIView):
    def get(self, request, pk):
        return Response(PaymentSerializer(payment_for(request.user, pk)).data)


class PaymentVoidView(APIView):
    def post(self, request, pk):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            PaymentSerializer(
                validation(
                    lambda: void_payment(
                        actor=request.user,
                        payment=payment_for(request.user, pk),
                        reason=serializer.validated_data["reason"],
                        request=request,
                    )
                )
            ).data
        )


class AllocationView(APIView):
    def post(self, request, pk):
        payment = payment_for(request.user, pk)
        serializer = AllocateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = invoice_for(request.user, serializer.validated_data["invoice_id"])
        allocation = validation(
            lambda: allocate_payment(
                actor=request.user,
                payment=payment,
                invoice=invoice,
                amount=serializer.validated_data["amount"],
                request=request,
            )
        )
        return Response({"id": allocation.id, "amount": allocation.amount}, status=201)


class OverviewView(APIView):
    def get(self, request):
        organization = organization_for(request.user, request.query_params.get("organization_id"))
        return Response(
            {
                currency: {
                    key: str(value) if hasattr(value, "as_tuple") else value
                    for key, value in values.items()
                }
                for currency, values in overview(organization).items()
            }
        )


class PlatformInvoiceView(InvoiceListCreateView):
    permission_classes = (PlatformSuperuser,)


class PlatformPaymentView(PaymentListCreateView):
    permission_classes = (PlatformSuperuser,)


class DeveloperInvoiceView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        key = authenticate_api_key(request.headers.get("Authorization", "")[7:], "finance.read")
        return Response(
            DeveloperInvoiceSerializer(
                Invoice.objects.filter(organization=key.client.organization)
                .select_related("booking")
                .prefetch_related("line_items", "allocations__payment")[:250],
                many=True,
            ).data
        )


class DeveloperPaymentView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        key = authenticate_api_key(request.headers.get("Authorization", "")[7:], "finance.read")
        return Response(
            DeveloperPaymentSerializer(
                Payment.objects.filter(organization=key.client.organization)[:250], many=True
            ).data
        )
