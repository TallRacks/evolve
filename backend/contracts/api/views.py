from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking
from contracts.models import (
    Contract,
    ContractApproval,
    ContractDocument,
    ContractParty,
    ContractSection,
    ContractTerm,
)
from contracts.selectors import artist_contracts_for_user, contract_activity, contracts_for_user
from contracts.services import (
    create_child,
    create_contract,
    create_from_booking,
    decide_approval,
    link_document,
    remove_child,
    request_approval,
    set_signing_status,
    transition_contract,
    unlink_document,
    update_child,
    update_contract,
)
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from white_label.services import authenticate_api_key

from .serializers import (
    ApprovalRequestSerializer,
    ApprovalSerializer,
    ContractDetailSerializer,
    ContractListSerializer,
    ContractWriteSerializer,
    DecisionSerializer,
    DocumentLinkSerializer,
    PartySerializer,
    SectionSerializer,
    SigningSerializer,
    StatusSerializer,
    TermSerializer,
)


def validation(operation):
    try:
        return operation()
    except DjangoPermissionDenied as error:
        raise PermissionDenied(str(error)) from error
    except DjangoValidationError as error:
        detail = error.message_dict if hasattr(error, "message_dict") else error.messages
        raise ValidationError(detail) from error


def organization_for(user, value, permission="contract.view"):
    organization = get_object_or_404(organizations_for_user(user), pk=value)
    if not user_has_organization_permission(user, organization, permission):
        raise PermissionDenied("You do not have Contract access for this organization.")
    return organization


def scoped_contract(user, pk):
    return get_object_or_404(contracts_for_user(user), pk=pk)


def detail(row):
    activity = [
        {
            "id": x.id,
            "action": x.action,
            "description": x.description,
            "actor": x.actor.email if x.actor else None,
            "created_at": x.created_at,
        }
        for x in contract_activity(row)
    ]
    return ContractDetailSerializer(row, context={"activity": activity}).data


class ContractListView(APIView):
    def get(self, request):
        organization = organization_for(request.user, request.query_params.get("organization_id"))
        rows = contracts_for_user(request.user).filter(organization=organization)
        q = request.query_params.get("q", "").strip()
        if q:
            rows = rows.filter(
                Q(reference__icontains=q)
                | Q(title__icontains=q)
                | Q(artist__stage_name__icontains=q)
                | Q(booking__reference__icontains=q)
                | Q(promoter__name__icontains=q)
            )
        for param, field in (
            ("artist_id", "artist_id"),
            ("booking_id", "booking_id"),
            ("promoter_id", "promoter_id"),
            ("contract_type", "contract_type"),
            ("status", "status"),
        ):
            if request.query_params.get(param):
                rows = rows.filter(**{field: request.query_params[param]})
        for param, field in (
            ("effective_from", "effective_date__gte"),
            ("expiry_to", "expiry_date__lte"),
        ):
            if request.query_params.get(param):
                value = parse_date(request.query_params[param])
                if not value:
                    raise ValidationError({param: "Enter a valid ISO date."})
                rows = rows.filter(**{field: value})
        try:
            offset = max(int(request.query_params.get("offset", 0)), 0)
        except ValueError as error:
            raise ValidationError({"offset": "Enter a valid integer."}) from error
        count = rows.count()
        return Response(
            {
                "count": count,
                "results": ContractListSerializer(rows[offset : offset + 50], many=True).data,
            }
        )

    def post(self, request):
        organization = organization_for(
            request.user, request.data.get("organization_id"), "contract.manage"
        )
        serializer = ContractWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = validation(
            lambda: create_contract(
                actor=request.user,
                organization=organization,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(detail(row), status=201)


class ContractDetailView(APIView):
    def get(self, request, contract_id):
        return Response(detail(scoped_contract(request.user, contract_id)))

    def patch(self, request, contract_id):
        row = scoped_contract(request.user, contract_id)
        serializer = ContractWriteSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(
            detail(
                validation(
                    lambda: update_contract(
                        row, actor=request.user, data=serializer.validated_data, request=request
                    )
                )
            )
        )


class ContractStatusView(APIView):
    def post(self, request, contract_id):
        row = scoped_contract(request.user, contract_id)
        serializer = StatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            detail(
                validation(
                    lambda: transition_contract(
                        row, actor=request.user, request=request, **serializer.validated_data
                    )
                )
            )
        )


CHILD_CONFIG = {
    "party": (ContractParty, PartySerializer),
    "term": (ContractTerm, TermSerializer),
    "section": (ContractSection, SectionSerializer),
}


class ChildListView(APIView):
    kind = None

    def get(self, request, contract_id):
        row = scoped_contract(request.user, contract_id)
        model, serializer = CHILD_CONFIG[self.kind]
        return Response(serializer(model.objects.filter(contract=row), many=True).data)

    def post(self, request, contract_id):
        row = scoped_contract(request.user, contract_id)
        _, serializer_class = CHILD_CONFIG[self.kind]
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        child = validation(
            lambda: create_child(
                self.kind, row, actor=request.user, data=serializer.validated_data, request=request
            )
        )
        return Response(serializer_class(child).data, status=201)


class ChildDetailView(APIView):
    kind = None

    def row(self, request, child_id):
        model, _ = CHILD_CONFIG[self.kind]
        return get_object_or_404(
            model.objects.select_related("contract__organization"),
            pk=child_id,
            contract__in=contracts_for_user(request.user),
        )

    def patch(self, request, child_id):
        row = self.row(request, child_id)
        _, serializer_class = CHILD_CONFIG[self.kind]
        serializer = serializer_class(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(
            serializer_class(
                validation(
                    lambda: update_child(
                        self.kind,
                        row,
                        actor=request.user,
                        data=serializer.validated_data,
                        request=request,
                    )
                )
            ).data
        )

    def delete(self, request, child_id):
        validation(
            lambda: remove_child(
                self.kind, self.row(request, child_id), actor=request.user, request=request
            )
        )
        return Response(status=204)


class SigningView(APIView):
    def post(self, request, party_id):
        row = get_object_or_404(
            ContractParty.objects.select_related("contract__organization"),
            pk=party_id,
            contract__in=contracts_for_user(request.user),
        )
        serializer = SigningSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            PartySerializer(
                validation(
                    lambda: set_signing_status(
                        row, actor=request.user, request=request, **serializer.validated_data
                    )
                )
            ).data
        )


class ApprovalListView(APIView):
    def get(self, request, contract_id):
        return Response(
            ApprovalSerializer(
                scoped_contract(request.user, contract_id).approvals.all(), many=True
            ).data
        )

    def post(self, request, contract_id):
        row = scoped_contract(request.user, contract_id)
        serializer = ApprovalRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approval = validation(
            lambda: request_approval(
                row, actor=request.user, request=request, **serializer.validated_data
            )
        )
        return Response(ApprovalSerializer(approval).data, status=201)


class ApprovalDecisionView(APIView):
    def post(self, request, approval_id):
        row = get_object_or_404(
            ContractApproval.objects.select_related("contract__organization", "membership__user"),
            pk=approval_id,
            contract__in=contracts_for_user(request.user),
        )
        serializer = DecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            ApprovalSerializer(
                validation(
                    lambda: decide_approval(
                        row, actor=request.user, request=request, **serializer.validated_data
                    )
                )
            ).data
        )


class DocumentListView(APIView):
    def post(self, request, contract_id):
        row = scoped_contract(request.user, contract_id)
        serializer = DocumentLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = validation(
            lambda: link_document(
                row, actor=request.user, request=request, **serializer.validated_data
            )
        )
        return Response({"id": link.id}, status=201)


class DocumentDetailView(APIView):
    def delete(self, request, link_id):
        row = get_object_or_404(
            ContractDocument.objects.select_related("contract__organization"),
            pk=link_id,
            contract__in=contracts_for_user(request.user),
        )
        validation(lambda: unlink_document(row, actor=request.user, request=request))
        return Response(status=204)


class BookingContractCreateView(APIView):
    def post(self, request, booking_id):
        booking = get_object_or_404(
            Booking.objects.select_related("organization", "artist", "promoter"),
            pk=booking_id,
            organization__in=organizations_for_user(request.user),
        )
        return Response(
            detail(
                validation(
                    lambda: create_from_booking(
                        actor=request.user, booking=booking, request=request
                    )
                )
            ),
            status=201,
        )


class ArtistContractView(APIView):
    def get(self, request):
        return Response(
            [
                {
                    "id": row.id,
                    "reference": row.reference,
                    "title": row.title,
                    "contract_type": row.contract_type,
                    "status": row.status,
                    "artist": row.artist_id,
                    "artist_name": row.artist.stage_name if row.artist else "",
                    "booking": row.booking_id,
                    "booking_reference": row.booking.reference if row.booking else "",
                    "effective_date": row.effective_date,
                    "expiry_date": row.expiry_date,
                    "is_expired": row.is_expired,
                    "updated_at": row.updated_at,
                }
                for row in artist_contracts_for_user(request.user)
            ]
        )


class PlatformContractListView(APIView):
    def get(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied("Platform superuser access required.")
        rows = contracts_for_user(request.user)
        if request.query_params.get("organization_id"):
            rows = rows.filter(organization_id=request.query_params["organization_id"])
        return Response(ContractListSerializer(rows[:200], many=True).data)


class PlatformContractDetailView(APIView):
    def get(self, request, contract_id):
        if not request.user.is_superuser:
            raise PermissionDenied("Platform superuser access required.")
        return Response(detail(get_object_or_404(contracts_for_user(request.user), pk=contract_id)))


class DeveloperContractView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Bearer "):
            raise AuthenticationFailed("A Bearer API key is required.")
        key = authenticate_api_key(header[7:], required_scope="contract.read")
        if not key:
            raise AuthenticationFailed("Invalid API key or scope.")
        rows = Contract.objects.filter(organization=key.client.organization).select_related(
            "artist", "booking"
        )
        return Response(
            [
                {
                    "id": x.id,
                    "reference": x.reference,
                    "title": x.title,
                    "type": x.contract_type,
                    "artist": x.artist.stage_name if x.artist else None,
                    "booking_reference": x.booking.reference if x.booking else None,
                    "status": x.status,
                    "effective_date": x.effective_date,
                    "expiry_date": x.expiry_date,
                }
                for x in rows
            ]
        )
