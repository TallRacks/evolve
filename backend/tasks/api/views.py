from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditEvent
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from tasks.selectors import tasks_for_user
from tasks.services import (
    add_checklist_item,
    create_task,
    remove_checklist_item,
    set_checklist_completion,
    transition_task,
    update_checklist_item,
    update_task,
)

from .serializers import ChecklistSerializer, TaskSerializer, TaskTransitionSerializer


class TaskAPIView(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            exc = ValidationError(detail)
        return super().handle_exception(exc)


def scoped_task(user, task_id):
    return get_object_or_404(
        tasks_for_user(user)
        .select_related("organization", "assigned_membership__user")
        .prefetch_related("checklist_items", "additional_assignees__user"),
        pk=task_id,
    )


class TaskListView(TaskAPIView):
    def get(self, request):
        queryset = (
            tasks_for_user(request.user)
            .select_related("assigned_membership__user")
            .prefetch_related("checklist_items", "additional_assignees__user")
        )
        if request.query_params.get("organization_id"):
            queryset = queryset.filter(organization_id=request.query_params["organization_id"])
        if request.query_params.get("mine") == "true":
            queryset = queryset.filter(Q(assigned_membership__user=request.user) | Q(additional_assignees__user=request.user))
        if request.query_params.get("workspace_id"):
            queryset = queryset.filter(
                source_document__workspace_id=request.query_params["workspace_id"]
            )
        for name in ("status", "priority", "release", "booking", "artist"):
            if request.query_params.get(name):
                queryset = queryset.filter(**{name: request.query_params[name]})
        return Response(TaskSerializer(queryset[:200], many=True).data)

    def post(self, request):
        organization = get_object_or_404(
            organizations_for_user(request.user), pk=request.data.get("organization_id")
        )
        serializer = TaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = create_task(
            actor=request.user,
            organization=organization,
            data=serializer.validated_data,
            request=request,
        )
        return Response(TaskSerializer(task).data, status=201)


class TaskDetailView(TaskAPIView):
    def get(self, request, task_id):
        task = scoped_task(request.user, task_id)
        data = TaskSerializer(task).data
        if user_has_organization_permission(request.user, task.organization, "task.view"):
            data["activity"] = [
                {
                    "id": item.id,
                    "action": item.action,
                    "description": item.description,
                    "actor": item.actor.email if item.actor else None,
                    "created_at": item.created_at,
                }
                for item in AuditEvent.objects.filter(
                    organization=task.organization,
                    resource_type="Task",
                    resource_id=str(task.pk),
                    action__startswith="task.",
                ).select_related("actor")[:100]
            ]
        return Response(data)

    def patch(self, request, task_id):
        task = scoped_task(request.user, task_id)
        serializer = TaskSerializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        task = update_task(
            actor=request.user, task=task, data=serializer.validated_data, request=request
        )
        return Response(TaskSerializer(task).data)


class TaskTransitionView(TaskAPIView):
    def post(self, request, task_id):
        task = scoped_task(request.user, task_id)
        serializer = TaskTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = transition_task(
            actor=request.user,
            task=task,
            to_status=serializer.validated_data["status"],
            request=request,
        )
        return Response(TaskSerializer(task).data)


class ChecklistListView(TaskAPIView):
    def post(self, request, task_id):
        task = scoped_task(request.user, task_id)
        serializer = ChecklistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = add_checklist_item(
            actor=request.user, task=task, request=request, **serializer.validated_data
        )
        return Response(ChecklistSerializer(item).data, status=201)


class ChecklistDetailView(TaskAPIView):
    def patch(self, request, task_id, item_id):
        task = scoped_task(request.user, task_id)
        item = get_object_or_404(task.checklist_items.filter(removed_at__isnull=True), pk=item_id)
        if "is_completed" in request.data:
            item = set_checklist_completion(
                actor=request.user,
                item=item,
                complete=serializers.BooleanField().run_validation(request.data["is_completed"]),
                request=request,
            )
        else:
            serializer = ChecklistSerializer(item, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            item = update_checklist_item(
                actor=request.user, item=item, data=serializer.validated_data, request=request
            )
        return Response(ChecklistSerializer(item).data)

    def delete(self, request, task_id, item_id):
        task = scoped_task(request.user, task_id)
        item = get_object_or_404(task.checklist_items.filter(removed_at__isnull=True), pk=item_id)
        remove_checklist_item(actor=request.user, item=item, request=request)
        return Response(status=204)
