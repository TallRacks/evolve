from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditEvent
from audit.services import record_event
from users.models import User

from ..models import Invitation, Membership, Organization
from ..ownership import validate_membership_owner_change, validate_user_deactivation
from ..permissions import user_has_organization_permission
from ..selectors import organizations_for_user
from ..services import accept_invitation, create_invitation, revoke_invitation
from .permissions import PlatformSuperuser
from .serializers import (
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    MembershipSerializer,
    MembershipUpdateSerializer,
    OrganizationSerializer,
    OrganizationUpdateSerializer,
    PlatformUserSerializer,
    ProfileSerializer,
)


def organization_queryset():
    now = timezone.now()
    return Organization.objects.annotate(
        member_count=Count("memberships", filter=Q(memberships__is_active=True), distinct=True),
        pending_invitation_count=Count(
            "invitations",
            filter=Q(
                invitations__accepted_at__isnull=True,
                invitations__revoked_at__isnull=True,
                invitations__expires_at__gt=now,
            ),
            distinct=True,
        ),
    )


def scoped_organization(user, organization_id):
    return get_object_or_404(
        organization_queryset().filter(pk__in=organizations_for_user(user).values("pk")),
        pk=organization_id,
    )


def require_permission(user, organization, permission):
    if not user_has_organization_permission(user, organization, permission):
        raise PermissionDenied("You do not have permission for this organization.")


class OrganizationListView(APIView):
    def get(self, request):
        organizations = organization_queryset().filter(
            pk__in=organizations_for_user(request.user).values("pk")
        )
        return Response(OrganizationSerializer(organizations, many=True).data)


class OrganizationDetailView(APIView):
    def get(self, request, organization_id):
        return Response(
            OrganizationSerializer(scoped_organization(request.user, organization_id)).data
        )

    def patch(self, request, organization_id):
        organization = scoped_organization(request.user, organization_id)
        require_permission(request.user, organization, "organization.manage")
        serializer = OrganizationUpdateSerializer(organization, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_event(
            actor=request.user,
            organization=organization,
            action="organization.updated",
            resource=organization,
            description=f"Updated organization {organization.name}.",
            request=request,
        )
        return Response(
            OrganizationSerializer(organization_queryset().get(pk=organization.pk)).data
        )


class OrganizationMemberListView(APIView):
    def get(self, request, organization_id, membership_id=None):
        organization = scoped_organization(request.user, organization_id)
        require_permission(request.user, organization, "membership.view")
        memberships = organization.memberships.select_related("user", "organization")
        return Response(MembershipSerializer(memberships, many=True).data)

    @transaction.atomic
    def patch(self, request, organization_id, membership_id):
        organization = scoped_organization(request.user, organization_id)
        require_permission(request.user, organization, "membership.manage")
        membership = get_object_or_404(
            Membership.objects.select_related("user", "organization"),
            pk=membership_id,
            organization=organization,
        )
        serializer = MembershipUpdateSerializer(membership, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        next_role = serializer.validated_data.get("role", membership.role)
        next_active = serializer.validated_data.get("is_active", membership.is_active)
        try:
            validate_membership_owner_change(membership, role=next_role, is_active=next_active)
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error
        serializer.save()
        record_event(
            actor=request.user,
            organization=organization,
            action="membership.updated",
            resource=membership,
            description=f"Updated membership for {membership.user.email}.",
            request=request,
        )
        return Response(MembershipSerializer(membership).data)


class OrganizationInvitationListView(APIView):
    def get(self, request, organization_id):
        organization = scoped_organization(request.user, organization_id)
        require_permission(request.user, organization, "membership.view")
        invitations = organization.invitations.select_related("invited_by")
        return Response(InvitationSerializer(invitations, many=True).data)

    def post(self, request, organization_id):
        organization = scoped_organization(request.user, organization_id)
        require_permission(request.user, organization, "membership.manage")
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = create_invitation(
            organization=organization,
            email=serializer.validated_data["email"],
            role=serializer.validated_data["role"],
            invited_by=request.user,
        )
        record_event(
            actor=request.user,
            organization=organization,
            action="invitation.created",
            resource=created.invitation,
            description=f"Created invitation for {created.invitation.email}.",
            request=request,
        )
        return Response(
            {**InvitationSerializer(created.invitation).data, "token": created.token},
            status=status.HTTP_201_CREATED,
        )


class InvitationDetailView(APIView):
    def post(self, request, invitation_id):
        invitation = get_object_or_404(
            Invitation.objects.select_related("organization"), pk=invitation_id
        )
        require_permission(request.user, invitation.organization, "membership.manage")
        revoked = revoke_invitation(invitation=invitation, revoked_by=request.user)
        record_event(
            actor=request.user,
            organization=revoked.organization,
            action="invitation.revoked",
            resource=revoked,
            description=f"Revoked invitation for {revoked.email}.",
            request=request,
        )
        return Response(InvitationSerializer(revoked).data)


class InvitationAcceptView(APIView):
    def post(self, request):
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            membership = accept_invitation(
                token=serializer.validated_data["token"], user=request.user
            )
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error
        record_event(
            actor=request.user,
            organization=membership.organization,
            action="invitation.accepted",
            resource=membership,
            description=f"Accepted invitation for {request.user.email}.",
            request=request,
        )
        return Response(MembershipSerializer(membership).data)


class ProfileView(APIView):
    def get(self, request):
        return Response(ProfileSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_event(
            actor=request.user,
            action="user.profile_updated",
            resource=request.user,
            description="Updated personal profile.",
            request=request,
        )
        return Response(serializer.data)


class PlatformOverviewView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        now = timezone.now()
        return Response(
            {
                "organizations": Organization.objects.count(),
                "active_organizations": Organization.objects.filter(is_active=True).count(),
                "users": User.objects.count(),
                "active_users": User.objects.filter(is_active=True).count(),
                "memberships": Membership.objects.count(),
                "pending_invitations": Invitation.objects.filter(
                    accepted_at__isnull=True, revoked_at__isnull=True, expires_at__gt=now
                ).count(),
                "recent_audit": AuditEvent.objects.count(),
            }
        )


class PlatformOrganizationListView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        return Response(OrganizationSerializer(organization_queryset(), many=True).data)

    def post(self, request):
        serializer = OrganizationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = serializer.save()
        record_event(
            actor=request.user,
            organization=organization,
            action="organization.created",
            resource=organization,
            description=f"Created organization {organization.name}.",
            request=request,
        )
        return Response(
            OrganizationSerializer(organization_queryset().get(pk=organization.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class PlatformOrganizationDetailView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request, organization_id):
        organization = get_object_or_404(organization_queryset(), pk=organization_id)
        data = OrganizationSerializer(organization).data
        data["members"] = MembershipSerializer(
            organization.memberships.select_related("user", "organization"), many=True
        ).data
        data["invitations"] = InvitationSerializer(
            organization.invitations.select_related("invited_by")[:50], many=True
        ).data
        return Response(data)

    def patch(self, request, organization_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        serializer = OrganizationSerializer(organization, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_event(
            actor=request.user,
            organization=organization,
            action="organization.updated",
            resource=organization,
            description=f"Updated organization {organization.name}.",
            request=request,
        )
        return Response(
            OrganizationSerializer(organization_queryset().get(pk=organization.pk)).data
        )


class PlatformUserListView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        users = User.objects.annotate(membership_count=Count("memberships"))
        return Response(PlatformUserSerializer(users, many=True).data)


class PlatformUserDetailView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request, user_id):
        user = get_object_or_404(
            User.objects.annotate(membership_count=Count("memberships")), pk=user_id
        )
        data = PlatformUserSerializer(user).data
        data["memberships"] = MembershipSerializer(
            user.memberships.select_related("user", "organization"), many=True
        ).data
        return Response(data)

    @transaction.atomic
    def patch(self, request, user_id):
        user = get_object_or_404(
            User.objects.annotate(membership_count=Count("memberships")), pk=user_id
        )
        if user == request.user and request.data.get("is_active") is False:
            raise ValidationError("You cannot deactivate your own platform account.")
        serializer = PlatformUserSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            validate_user_deactivation(
                user,
                is_active=serializer.validated_data.get("is_active", user.is_active),
            )
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error
        serializer.save()
        record_event(
            actor=request.user,
            action="user.updated",
            resource=user,
            description=f"Updated user {user.email}.",
            request=request,
        )
        return Response(serializer.data)
