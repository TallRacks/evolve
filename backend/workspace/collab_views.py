import re

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.services import create_notification
from organizations.models import Membership
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user

from .collaboration_models import Comment, CommentMention
from documents.models import DocumentCollaborator

def user_display_name(user):
    return f"{user.first_name} {user.last_name}".strip() or user.email


CONTEXT_PERMISSIONS = {
    "document": "document.view",
    "task": "task.view",
    "booking": "booking.view",
    "campaign": "campaign.view",
    "production": "production.view",
}


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = (
            "id",
            "organization",
            "author",
            "context_type",
            "context_id",
            "parent_comment",
            "body",
            "created_at",
            "updated_at",
            "edited_at",
            "resolved_at",
            "resolved_by",
        )
        read_only_fields = ("id", "organization", "author", "created_at", "updated_at", "edited_at", "resolved_at", "resolved_by")


def scoped_org(request, organization_id):
    return get_object_or_404(organizations_for_user(request.user), pk=organization_id)


def mention_memberships(body, organization):
    names = {value.lower() for value in re.findall(r"@([A-Za-z0-9._-]{2,80})", body)}
    memberships = (
        Membership.objects.active().filter(organization=organization).select_related("user")
    )
    return [
        item
        for item in memberships
        if item.user.email.lower() in names
        or user_display_name(item.user).lower().replace(" ", ".") in names
    ]


class CommentListView(APIView):
    def get(self, request):
        organization = scoped_org(request, request.query_params.get("organization_id"))
        context_type = request.query_params.get("context_type")
        context_id = request.query_params.get("context_id")
        queryset = Comment.objects.filter(organization=organization, archived_at__isnull=True)
        if context_type in CONTEXT_PERMISSIONS and context_id:
            if context_type == "document":
                from documents.selectors import documents_for_user

                if not documents_for_user(request.user, organization).filter(pk=context_id).exists():
                    raise PermissionDenied()
            queryset = queryset.filter(context_type=context_type, context_id=context_id)
        return Response(CommentSerializer(queryset.select_related("author")[:100], many=True).data)

    def post(self, request):
        organization = scoped_org(request, request.data.get("organization_id"))
        context_type = request.data.get("context_type")
        if context_type not in CONTEXT_PERMISSIONS or not user_has_organization_permission(
            request.user, organization, CONTEXT_PERMISSIONS[context_type]
        ):
            raise PermissionDenied()
        if context_type == "document":
            from documents.selectors import documents_for_user

            document = (
                documents_for_user(request.user, organization)
                .filter(pk=request.data.get("context_id"))
                .first()
            )
            if document is None:
                raise PermissionDenied()
            collaborator_role = (
                DocumentCollaborator.objects.filter(document=document, user=request.user)
                .values_list("role", flat=True)
                .first()
            )
            can_comment = collaborator_role in {
                DocumentCollaborator.Role.COMMENT,
                DocumentCollaborator.Role.EDIT,
                DocumentCollaborator.Role.MANAGE,
            }
            can_comment = (
                can_comment
                or document.uploaded_by_id == request.user.pk
                or user_has_organization_permission(request.user, organization, "document.manage")
            )
            if not can_comment:
                raise PermissionDenied()
        parent = None
        if request.data.get("parent_comment"):
            parent = get_object_or_404(
                Comment,
                pk=request.data["parent_comment"],
                organization=organization,
                context_type=context_type,
                context_id=request.data.get("context_id"),
                archived_at__isnull=True,
            )
        serializer = CommentSerializer(
            data={
                "context_type": context_type,
                "context_id": request.data.get("context_id"),
                "parent_comment": parent.pk if parent else None,
                "body": request.data.get("body", ""),
            }
        )
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(organization=organization, author=request.user)
        mentioned = mention_memberships(comment.body, organization)
        CommentMention.objects.bulk_create(
            [CommentMention(comment=comment, membership=item) for item in mentioned],
            ignore_conflicts=True,
        )
        if mentioned:
            create_notification(
                organization=organization,
                notification_type="comment.mentioned",
                category="team",
                title=f"{user_display_name(request.user)} mentioned you",
                message=comment.body[:1000],
                users=[item.user for item in mentioned],
                actor=request.user,
                action_url=f"/workspace/{context_type}/{comment.context_id}",
            )
        return Response(CommentSerializer(comment).data, status=201)


class CommentDetailView(APIView):
    def patch(self, request, comment_id):
        comment = get_object_or_404(
            Comment,
            pk=comment_id,
            organization__in=organizations_for_user(request.user),
            archived_at__isnull=True,
        )
        action = request.data.get("action")
        if action in {"resolve", "reopen"}:
            can_manage = comment.author_id == request.user.pk or user_has_organization_permission(
                request.user, comment.organization, "document.manage"
            )
            if not can_manage:
                raise PermissionDenied()
            comment.resolved_at = timezone.now() if action == "resolve" else None
            comment.resolved_by = request.user if action == "resolve" else None
            comment.save(update_fields=["resolved_at", "resolved_by", "updated_at"])
            return Response(CommentSerializer(comment).data)
        if comment.author_id != request.user.pk:
            raise PermissionDenied()
        body = request.data.get("body", "")
        if not isinstance(body, str) or not body.strip() or len(body) > 5000:
            raise ValidationError({"body": "Plain-text comment is required."})
        comment.body = body
        comment.edited_at = timezone.now()
        comment.save(update_fields=["body", "edited_at", "updated_at"])
        return Response(CommentSerializer(comment).data)

    def delete(self, request, comment_id):
        comment = get_object_or_404(
            Comment,
            pk=comment_id,
            organization__in=organizations_for_user(request.user),
            archived_at__isnull=True,
        )
        if comment.author_id != request.user.pk and not user_has_organization_permission(
            request.user, comment.organization, "organization.manage"
        ):
            raise PermissionDenied()
        comment.archived_at = timezone.now()
        comment.save(update_fields=["archived_at", "updated_at"])
        return Response(status=204)
