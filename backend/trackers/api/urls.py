from django.urls import path
from .views import TrackerDetailView, TrackerHistoryView, TrackerSchemaView, TrackerSyncView, TrackerView
urlpatterns=[path("trackers/", TrackerView.as_view()), path("trackers/<uuid:pk>/", TrackerDetailView.as_view()), path("trackers/<uuid:pk>/sync/", TrackerSyncView.as_view()), path("trackers/<uuid:pk>/schema/", TrackerSchemaView.as_view()), path("trackers/<uuid:pk>/history/", TrackerHistoryView.as_view())]
