from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from artists.models import Artist
from documents.file_validation import validate_upload
from documents.models import Document
from documents.services import upload_document
from documents.storage import DocumentStorageUnavailable
from audit.models import AuditEvent
from audit.services import record_event
from bookings.models import Booking
from callsheets.models import CallSheet, CallSheetVersion
from contacts.models import Contact
from promoters.models import Promoter
from users.mobile_services import revoke_all_devices
from users.models import User
from venues.models import Venue

from ..models import FeatureSetting, Invitation, Membership, Organization, RoleProfile
from ..ownership import validate_membership_owner_change, validate_user_deactivation
from ..permissions import role_catalog, user_has_organization_permission
from ..selectors import organizations_for_user
from ..services import accept_invitation, create_invitation, revoke_invitation, signup_invitation
from .permissions import PlatformSuperuser
from .serializers import (
    InvitationAcceptSerializer,
    InvitationSignupSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    MembershipCreateSerializer,
    MembershipSerializer,
    MembershipUpdateSerializer,
    OrganizationSerializer,
    OrganizationUpdateSerializer,
    PlatformUserSerializer,
    ProfileSerializer,
    FeatureSettingSerializer,
    RoleProfileSerializer,
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
        artist_count=Count("artists", distinct=True),
        active_artist_count=Count("artists", filter=Q(artists__status="active"), distinct=True),
        inactive_artist_count=Count(
            "artists",
            filter=Q(artists__status__in=("inactive", "archived")),
            distinct=True,
        ),
        promoter_count=Count("promoters", distinct=True),
        venue_count=Count("venues", distinct=True),
        contact_count=Count("contacts", distinct=True),
        booking_count=Count("bookings", distinct=True),
        upcoming_booking_count=Count(
            "bookings",
            filter=Q(bookings__event_date__gte=timezone.localdate()),
            distinct=True,
        ),
        confirmed_booking_count=Count(
            "bookings", filter=Q(bookings__status="confirmed"), distinct=True
        ),
        pending_booking_count=Count(
            "bookings",
            filter=Q(bookings__status__in=("enquiry", "hold", "pending")),
            distinct=True,
        ),
        priority_booking_count=Count(
            "bookings",
            filter=Q(bookings__priority__in=("high", "urgent"), bookings__event_date__gte=timezone.localdate()),
            distinct=True,
        ),
        call_sheet_count=Count("call_sheets", distinct=True),
        draft_call_sheet_count=Count(
            "call_sheets__versions",
            filter=Q(call_sheets__versions__status__in=("draft", "ready")),
            distinct=True,
        ),
        published_upcoming_call_sheet_count=Count(
            "call_sheets__versions",
            filter=Q(
                call_sheets__versions__status="published",
                call_sheets__versions__event_date__gte=timezone.localdate(),
            ),
            distinct=True,
        ),
        confirmed_without_call_sheet_count=Count(
            "bookings",
            filter=Q(
                bookings__status="confirmed",
                bookings__event_date__gte=timezone.localdate(),
                bookings__call_sheet__isnull=True,
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


class RoleCatalogView(APIView):
    def get(self, request):
        return Response(role_catalog())


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


def create_membership(*, actor, organization, data, request):
    user = get_object_or_404(User, pk=data.pop("user_id"), is_active=True)
    if Membership.objects.filter(user=user, organization=organization).exists():
        raise ValidationError("This user already has a membership in the organization.")
    membership = Membership.objects.create(user=user, organization=organization, **data)
    record_event(
        actor=actor,
        organization=organization,
        action="membership.created",
        resource=membership,
        description=f"Added {user.email} to the organization as {membership.role}.",
        request=request,
    )
    return membership


class OrganizationMemberListView(APIView):
    @transaction.atomic
    def post(self, request, organization_id, membership_id=None):
        if membership_id is not None:
            return Response({"detail": "Membership detail URLs do not accept POST."}, status=405)
        organization = scoped_organization(request.user, organization_id)
        require_permission(request.user, organization, "membership.manage")
        serializer = MembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = create_membership(
            actor=request.user,
            organization=organization,
            data=dict(serializer.validated_data),
            request=request,
        )
        return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)

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
        from notifications.models import EmailDeliveryAttempt

        attempt = EmailDeliveryAttempt.objects.filter(
            idempotency_key=f"invitation:{created.invitation.pk}"
        ).first()
        return Response(
            {
                **InvitationSerializer(created.invitation).data,
                "token": created.token,
                "email_delivery_status": attempt.status if attempt else "pending",
            },
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


class InvitationSignupView(APIView):
    permission_classes = ()

    def post(self, request):
        serializer = InvitationSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from django.contrib.auth.password_validation import validate_password
        try:
            validate_password(serializer.validated_data["password"])
            user, membership = signup_invitation(**serializer.validated_data)
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error
        record_event(actor=user, organization=membership.organization, action="invitation.signup_completed", resource=membership, description="Completed invitation signup.", request=request)
        return Response({"email": user.email, "organization": membership.organization.name}, status=status.HTTP_201_CREATED)


class ProfileImageView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def get(self, request):
        document = request.user.profile_image_document
        if not document:
            raise ValidationError("No profile image has been uploaded.")
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(f"/api/documents/{document.pk}/preview/?organization={document.organization_id}")

    def post(self, request):
        membership = request.user.memberships.active().select_related("organization").first()
        if not membership:
            raise PermissionDenied("An active organization membership is required.")
        file = request.FILES.get("file")
        if not file:
            raise ValidationError({"file": "Choose an image to upload."})
        try:
            metadata = validate_upload(file, document_type=Document.Type.OTHER)
            if not metadata["content_type"].startswith("image/"):
                raise ValidationError({"file": "Profile pictures must be PNG, JPEG, or WebP images."})
            document = upload_document(
                actor=request.user, organization=membership.organization, file=file, request=request,
                title="Profile picture", document_type=Document.Type.OTHER,
                visibility=Document.Visibility.PRIVATE,
            )
        except DocumentStorageUnavailable as error:
            raise ValidationError(str(error)) from error
        request.user.profile_image_document = document
        request.user.save(update_fields=("profile_image_document", "updated_at"))
        record_event(actor=request.user, organization=membership.organization, action="user.profile_image_uploaded", resource=request.user, description="Uploaded a profile image.", request=request)
        return Response(ProfileSerializer(request.user, context={"request": request}).data)


class ProfileView(APIView):
    def get(self, request):
        return Response(ProfileSerializer(request.user, context={"request": request}).data)

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
                    accepted_at__isnull=True,
                    revoked_at__isnull=True,
                    expires_at__gt=now,
                ).count(),
                "recent_audit": AuditEvent.objects.count(),
                "artists": Artist.objects.count(),
                "active_artists": Artist.objects.filter(status="active").count(),
                "promoters": Promoter.objects.count(),
                "venues": Venue.objects.count(),
                "contacts": Contact.objects.count(),
                "bookings": Booking.objects.count(),
                "upcoming_bookings": Booking.objects.filter(
                    event_date__gte=timezone.localdate()
                ).count(),
                "call_sheets": CallSheet.objects.count(),
                "draft_call_sheets": CallSheetVersion.objects.filter(
                    status__in=("draft", "ready")
                ).count(),
                "published_upcoming_call_sheets": CallSheetVersion.objects.filter(
                    status="published", event_date__gte=timezone.localdate()
                ).count(),
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


class PlatformOrganizationMemberListView(APIView):
    permission_classes = (PlatformSuperuser,)

    @transaction.atomic
    def post(self, request, organization_id):
        organization = get_object_or_404(Organization, pk=organization_id, is_active=True)
        serializer = MembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = create_membership(
            actor=request.user,
            organization=organization,
            data=dict(serializer.validated_data),
            request=request,
        )
        return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


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
        was_active = user.is_active
        serializer.save()
        if was_active and not user.is_active:
            revoke_all_devices(user)
        record_event(
            actor=request.user,
            action="user.updated",
            resource=user,
            description=f"Updated user {user.email}.",
            request=request,
        )
        return Response(serializer.data)


FEATURE_CATALOG = (
    ("activity", "Activity", "Organization activity stream."),
    ("reports", "Reports", "Operational reporting surfaces."),
    ("boards", "Boards", "Workspace boards."),
    ("office", "Office Home", "Office documents and sheets."),
    ("booking-tracker", "Booking Tracker", "Google Sheets booking tracker tools."),
    ("booking-options", "Booking Options", "Booking option configuration."),
    ("file-uploader", "File Uploader", "Shared document upload surface."),
    ("mailroom", "Mailroom", "Mailbox workspace."),
    ("signing", "Signing Workspace", "Document signing tools."),
    ("template-editor", "Template Editor", "Template configuration tools."),
)

def ensure_feature_settings(organization):
    existing = {item.key: item for item in organization.feature_settings.all()}
    for key, label, description in FEATURE_CATALOG:
        if key not in existing:
            existing[key] = FeatureSetting.objects.create(organization=organization, key=key, label=label, description=description)
    return list(sorted(existing.values(), key=lambda item: item.label.lower()))


class FeatureSettingListView(APIView):
    def get(self, request, organization_id):
        organization = scoped_organization(request.user, organization_id)
        require_permission(request.user, organization, "membership.view")
        return Response(FeatureSettingSerializer(ensure_feature_settings(organization), many=True).data)

    @transaction.atomic
    def patch(self, request, organization_id, feature_id):
        organization = scoped_organization(request.user, organization_id)
        require_permission(request.user, organization, "membership.manage")
        feature = get_object_or_404(FeatureSetting, pk=feature_id, organization=organization)
        serializer = FeatureSettingSerializer(feature, data={"is_enabled": request.data.get("is_enabled")}, partial=True)
        serializer.is_valid(raise_exception=True)
        feature = serializer.save()
        record_event(actor=request.user, organization=organization, action="feature.updated", resource=feature, description=f"Updated feature setting {feature.key}.", request=request)
        return Response(FeatureSettingSerializer(feature).data)


class MembershipScopePreviewView(APIView):
    def get(self, request, organization_id, membership_id):
        organization = scoped_organization(request.user, organization_id)
        require_permission(request.user, organization, "membership.manage")
        membership = get_object_or_404(Membership.objects.select_related("user", "role_profile"), pk=membership_id, organization=organization)
        from ..permissions import all_permissions, user_has_organization_permission
        permissions = [permission for permission in all_permissions() if user_has_organization_permission(membership.user, organization, permission)]
        features = ensure_feature_settings(organization)
        return Response({"membership_id": str(membership.id), "user": {"email": membership.user.email, "name": membership.user.get_full_name()}, "role": membership.role, "role_profile": membership.role_profile.name if membership.role_profile else None, "permissions": permissions, "features": FeatureSettingSerializer(features, many=True).data})


class RoleProfileListCreateView(APIView):
    def get(self, request, organization_id):
        organization = scoped_organization(request.user, organization_id)
        require_permission(request.user, organization, "membership.view")
        return Response(RoleProfileSerializer(organization.role_profiles.all(), many=True).data)

    @transaction.atomic
    def post(self, request, organization_id):
        organization = scoped_organization(request.user, organization_id)
        require_permission(request.user, organization, "membership.manage")
        serializer = RoleProfileSerializer(data={**request.data, "organization": organization.id})
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        record_event(actor=request.user, organization=organization, action="role_profile.created", resource=profile, description=f"Created role profile {profile.name}.", request=request)
        return Response(RoleProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


class RoleProfileDetailView(APIView):
    @transaction.atomic
    def patch(self, request, organization_id, profile_id):
        organization = scoped_organization(request.user, organization_id)
        require_permission(request.user, organization, "membership.manage")
        profile = get_object_or_404(RoleProfile, pk=profile_id, organization=organization)
        serializer = RoleProfileSerializer(profile, data={**request.data, "organization": organization.id}, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        record_event(actor=request.user, organization=organization, action="role_profile.updated", resource=profile, description=f"Updated role profile {profile.name}.", request=request)
        return Response(RoleProfileSerializer(profile).data)
