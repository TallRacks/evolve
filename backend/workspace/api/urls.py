from django.urls import path

from ..domain_views import ApprovalHubView, BoardView
from ..channel_settings_views import ChannelSettingsView
from ..collab_views import CommentDetailView, CommentListView
from ..channel_views import (
    ChannelConnectView,
    ChannelDisconnectView,
    InboundEmailWebhookView,
    WhatsAppWebhookView,
)
from .views import (
    ActionExecuteView,
    ActionProposeView,
    AutomationListView,
    CopilotView,
    MyWorkView,
    PlatformAIView,
    WorkspaceInboxView,
    WorkspaceListView,
    WorkspaceSummaryView,
    WorkspaceDetailView,
    BoardDetailView,
    WorkspaceBoardView,
    DailySummaryView,
)

urlpatterns = [
    path("workspace/channels/", ChannelSettingsView.as_view()),
    path("platform/channels/", ChannelSettingsView.as_view()),
    path("workspace/approvals/", ApprovalHubView.as_view()),
    path("workspace/boards/<str:board_key>/", BoardView.as_view()),
    path("workspaces/", WorkspaceListView.as_view()),
    path("workspaces/<uuid:workspace_id>/summary/", WorkspaceSummaryView.as_view()),
    path("workspaces/<uuid:workspace_id>/boards/", WorkspaceBoardView.as_view()),
    path("workspaces/<uuid:workspace_id>/", WorkspaceDetailView.as_view()),
    path("workspace/summary/", DailySummaryView.as_view()),
    path("boards/<uuid:board_id>/", BoardDetailView.as_view()),
    path("boards/<uuid:board_id>/<str:action>/", BoardDetailView.as_view()),
    path("workspace/comments/", CommentListView.as_view()),
    path("workspace/comments/<uuid:comment_id>/", CommentDetailView.as_view()),
    path("messaging/webhooks/whatsapp/<uuid:connector_id>/", WhatsAppWebhookView.as_view()),
    path("messaging/webhooks/email/<uuid:connector_id>/", InboundEmailWebhookView.as_view()),
    path("workspace/channels/connect/", ChannelConnectView.as_view()),
    path("workspace/channels/<uuid:identity_id>/disconnect/", ChannelDisconnectView.as_view()),
    path("workspace/actions/", ActionProposeView.as_view()),
    path("workspace/actions/<uuid:action_id>/execute/", ActionExecuteView.as_view()),
    path("workspace/copilot/", CopilotView.as_view()),
    path("workspace/my-work/", MyWorkView.as_view()),
    path("workspace/inbox/", WorkspaceInboxView.as_view()),
    path("workspace/automations/", AutomationListView.as_view()),
    path("platform/ai/", PlatformAIView.as_view()),
]
