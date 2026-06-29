
from django.urls import path
from .api_views import (
    DashboardSummaryAPIView,
    DashboardChartsAPIView,
    AttendanceAllAPIView,
    AttendancePresentAPIView,
    AttendanceLateAPIView,
    AttendanceAbsentAPIView,
    AttendanceExportAPIView,
    AttendanceDownloadArchiveAPIView,
    EmployeeListCreateAPIView,
    EmployeeUploadFaceAPIView,
)

urlpatterns = [
    # Dashboard & Statistics
    path("dashboard/summary/", DashboardSummaryAPIView.as_view(), name="v1-dashboard-summary"),
    path("dashboard/charts/", DashboardChartsAPIView.as_view(), name="v1-dashboard-charts"),

    # Attendance Lists & Export
    path("attendance/all/", AttendanceAllAPIView.as_view(), name="v1-attendance-all"),
    path("attendance/present/", AttendancePresentAPIView.as_view(), name="v1-attendance-present"),
    path("attendance/late/", AttendanceLateAPIView.as_view(), name="v1-attendance-late"),
    path("attendance/absent/", AttendanceAbsentAPIView.as_view(), name="v1-attendance-absent"),
    path("attendance/export/", AttendanceExportAPIView.as_view(), name="v1-attendance-export"),
    path("attendance/download-archive/", AttendanceDownloadArchiveAPIView.as_view(), name="v1-attendance-download-archive"),

    # Employee Management
    path("employees/", EmployeeListCreateAPIView.as_view(), name="v1-employees-list-create"),
    path("employees/<int:id>/upload-face/", EmployeeUploadFaceAPIView.as_view(), name="v1-employees-upload-face"),
]
