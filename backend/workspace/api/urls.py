from django.urls import path

from .views import (
    ActionExecuteView,
    ActionProposeView,
    AutomationListView,
    CopilotView,
    MyWorkView,
    PlatformAIView,
    WorkspaceInboxView,
)

urlpatterns = [
    path("workspace/actions/", ActionProposeView.as_view()),
    path("workspace/actions/<uuid:action_id>/execute/", ActionExecuteView.as_view()),
    path("workspace/copilot/", CopilotView.as_view()),
    path("workspace/my-work/", MyWorkView.as_view()),
    path("workspace/inbox/", WorkspaceInboxView.as_view()),
    path("workspace/automations/", AutomationListView.as_view()),
    path("platform/ai/", PlatformAIView.as_view()),
]
