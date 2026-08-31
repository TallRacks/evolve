from django.urls import path

from .views import ReportExportView, ReportView, SavedViewCollection, SavedViewDetail

urlpatterns = [
    path("reports/", ReportView.as_view()),
    path("reports/export/", ReportExportView.as_view()),
    path("reports/saved-views/", SavedViewCollection.as_view()),
    path("reports/saved-views/<uuid:pk>/", SavedViewDetail.as_view()),
    path("reports/<str:report_key>/export/", ReportExportView.as_view()),
    path("reports/<str:report_key>/", ReportView.as_view()),
]
