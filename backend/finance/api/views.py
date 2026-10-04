from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import record_event
from bookings.models import Booking
from documents.models import Document
from documents.services import upload_document
from documents.storage import DocumentStorageUnavailable
from finance.models import (
    EmployeeInvoiceSubmission,
    FinanceProfile,
    Invoice,
    InvoiceLineItem,
    Payment,
    Quote,
    QuoteLineItem,
)
from finance.selectors import invoices_for_user, overview, payments_for_user
from finance.services import (
    add_line_item,
    allocate_payment,
    create_invoice,
    create_invoice_from_booking,
    finance_users,
    issue_invoice,
    record_payment,
    remove_line_item,
    require,
    update_invoice,
    update_line_item,
    void_invoice,
    void_payment,
)
from notifications.services import create_notification
from organizations.api.permissions import PlatformSuperuser
from organizations.models import Organization
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from white_label.services import authenticate_api_key

from .serializers import (
    AllocateSerializer,
    DeveloperInvoiceSerializer,
    DeveloperPaymentSerializer,
    EmployeeInvoiceCreateSerializer,
    EmployeeInvoiceSubmissionSerializer,
    FinanceProfileSerializer,
    InvoiceCreateSerializer,
    InvoiceSerializer,
    InvoiceUpdateSerializer,
    LineItemSerializer,
    PaymentCreateSerializer,
    PaymentSerializer,
    QuoteSerializer,
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
            ("promoter", "booking__promoter_id"),
        ):
            if request.query_params.get(parameter):
                qs = qs.filter(**{field: request.query_params[parameter]})
        event = request.query_params.get("event", "").strip()
        if event:
            qs = qs.filter(booking__title__icontains=event)
        promoter_name = request.query_params.get("promoter_name", "").strip()
        if promoter_name:
            qs = qs.filter(booking__promoter_name_snapshot__icontains=promoter_name)
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


class PaymentProofUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, pk):
        payment = payment_for(request.user, pk)
        require(request.user, payment.organization, "finance.manage")
        file = request.FILES.get("file")
        if not file:
            raise ValidationError({"file": "A proof-of-payment file is required."})
        if file.size > 4 * 1024 * 1024 * 1024:
            raise ValidationError({"file": "Files must be 4GB or smaller."})
        try:
            document = upload_document(
                actor=request.user, organization=payment.organization, file=file, request=request,
                title=f"Proof of payment - {payment.payment_reference}",
                document_type=Document.Type.RECEIPT, description="Private proof of payment.",
                visibility=Document.Visibility.RESTRICTED,
            )
        except (DjangoValidationError, DocumentStorageUnavailable) as exc:
            raise ValidationError({"file": str(exc)}) from exc
        payment.proof_document = document
        payment.save(update_fields=["proof_document", "updated_at"])
        return Response(PaymentSerializer(payment).data)


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


class EmployeeInvoiceSubmissionView(APIView):
    def _queryset(self, request, organization):
        qs = EmployeeInvoiceSubmission.objects.filter(
            organization=organization
        ).select_related("employee", "settled_invoice")
        if not user_has_organization_permission(request.user, organization, "finance.manage"):
            qs = qs.filter(employee=request.user)
        return qs.order_by("-created_at")

    def get(self, request):
        organization = organization_for(request.user, request.query_params.get("organization_id"))
        qs = self._queryset(request, organization)
        return Response(EmployeeInvoiceSubmissionSerializer(qs[:250], many=True).data)

    def post(self, request):
        serializer = EmployeeInvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = organization_for(
            request.user, serializer.validated_data["organization_id"], "finance.view"
        )
        line_items = serializer.validated_data["line_items"]
        total = serializer.context["total_amount"]
        submission = EmployeeInvoiceSubmission.objects.create(
            organization=organization,
            employee=request.user,
            submission_number=f"EMP-{timezone.now().year}-{timezone.now().strftime('%m%d%H%M%S')}",
            invoice_date=serializer.validated_data["invoice_date"],
            currency=serializer.validated_data["currency"],
            line_items=line_items,
            total_amount=total,
            notes=serializer.validated_data.get("notes", ""),
        )
        record_event(
            actor=request.user,
            organization=organization,
            action="finance.employee_invoice_submitted",
            resource=submission,
            description=f"Submitted employee invoice {submission.submission_number}.",
            request=request,
        )
        create_notification(
            organization=organization,
            notification_type="finance.employee_invoice_submitted",
            category="finance",
            title="Employee invoice submitted",
            message=(
                f"{request.user.get_full_name() or request.user.email} submitted "
                f"{submission.submission_number} for review."
            ),
            users=finance_users(organization),
            actor=request.user,
            source=submission,
            action_url="/workspace/finance/employee-invoices",
        )
        return Response(EmployeeInvoiceSubmissionSerializer(submission).data, status=201)


class EmployeeInvoiceSubmissionDetailView(APIView):
    def patch(self, request, pk):
        submission = get_object_or_404(
            EmployeeInvoiceSubmission.objects.select_related("organization", "employee"),
            pk=pk,
        )
        if not user_has_organization_permission(
            request.user, submission.organization, "finance.manage"
        ):
            raise ValidationError("Only finance managers can update employee invoice status.")
        status = str(request.data.get("status", "")).strip()
        allowed = {choice for choice, _ in EmployeeInvoiceSubmission.Status.choices}
        if status not in allowed:
            raise ValidationError({"status": "Choose a valid employee invoice status."})
        submission.status = status
        submission.save(update_fields=("status", "updated_at"))
        create_notification(
            organization=submission.organization,
            notification_type="finance.employee_invoice_status",
            category="finance",
            title="Employee invoice updated",
            message=(
                f"{submission.submission_number} is now "
                f"{submission.get_status_display().lower()}."
            ),
            users=[submission.employee],
            actor=request.user,
            source=submission,
            action_url="/workspace/finance/employee-invoices",
        )
        record_event(
            actor=request.user,
            organization=submission.organization,
            action="finance.employee_invoice_status_changed",
            resource=submission,
            description=f"Updated employee invoice {submission.submission_number} status.",
            request=request,
        )
        return Response(EmployeeInvoiceSubmissionSerializer(submission).data)


class FinanceProfileView(APIView):
    def get(self, request):
        organization = organization_for(
            request.user, request.query_params.get("organization_id")
        )
        profile, _ = FinanceProfile.objects.get_or_create(organization=organization)
        return Response(FinanceProfileSerializer(profile).data)

    def patch(self, request):
        organization = organization_for(
            request.user, request.data.get("organization_id"), "finance.manage"
        )
        profile, _ = FinanceProfile.objects.get_or_create(organization=organization)
        serializer = FinanceProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class QuoteListCreateView(APIView):
    def get(self, request):
        organization = organization_for(
            request.user, request.query_params.get("organization_id")
        )
        quotes = Quote.objects.filter(organization=organization).prefetch_related(
            "line_items"
        )[:250]
        return Response(QuoteSerializer(quotes, many=True).data)

    def post(self, request):
        organization = organization_for(
            request.user, request.data.get("organization_id"), "finance.manage"
        )
        profile, _ = FinanceProfile.objects.get_or_create(organization=organization)
        number = f"{profile.quote_prefix}-{timezone.now().year}-{profile.next_quote_number:04d}"
        profile.next_quote_number += 1
        profile.save(update_fields=("next_quote_number", "updated_at"))
        data = {
            key: request.data.get(key)
            for key in (
                "billed_to_name",
                "billed_to_email",
                "currency",
                "valid_until",
                "tax_amount",
                "notes",
            )
            if key in request.data
        }
        data.setdefault("currency", profile.default_currency)
        quote = Quote.objects.create(
            organization=organization,
            quote_number=number,
            created_by=request.user,
            **data,
        )
        for sequence, item in enumerate(request.data.get("line_items", []), start=1):
            if not isinstance(item, dict) or not str(item.get("description", "")).strip():
                raise ValidationError({"line_items": "Each quote line needs a description."})
            QuoteLineItem.objects.create(
                quote=quote,
                description=str(item["description"]).strip(),
                quantity=item.get("quantity", "1"),
                unit_amount=item.get("unit_amount", "0"),
                sequence=sequence,
            )
        return Response(QuoteSerializer(quote).data, status=201)
