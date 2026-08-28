from django.urls import path

from .views import (
    ChecklistDetailView,
    ChecklistListView,
    TaskDetailView,
    TaskListView,
    TaskTransitionView,
)

urlpatterns = [
    path("tasks/", TaskListView.as_view()),
    path("tasks/<uuid:task_id>/", TaskDetailView.as_view()),
    path("tasks/<uuid:task_id>/status/", TaskTransitionView.as_view()),
    path("tasks/<uuid:task_id>/checklist/", ChecklistListView.as_view()),
    path(
        "tasks/<uuid:task_id>/checklist/<uuid:item_id>/",
        ChecklistDetailView.as_view(),
    ),
]
