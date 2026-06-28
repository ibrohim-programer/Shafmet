from django.urls import path

from .views import (
    AttendanceByDateView,
    AttendanceListView,
    AttendanceRetrieveView,
    AttendanceStatsView,
    CheckInView,
    CreateWorkerView,
    MyAttendanceListView,
    WorkerListView,
    WorkerRetrieveUpdateDestroyView,
    WorkZoneListCreateView,
    WorkZoneRetrieveUpdateDestroyView,
    WorkScheduleListCreateView,
    WorkScheduleRetrieveUpdateDestroyView,
    FaceCheckInOutView,
    MyAttendanceTodayView,
    WorkerAttendanceDetailView,
    AttendanceHistoryView,
    WorkerSearchView,
)

urlpatterns = [
    # Workers
    path("workers/create/", CreateWorkerView.as_view(), name="inspection-create-worker"),
    path("workers/", WorkerListView.as_view(), name="inspection-worker-list"),
    path("workers/search/", WorkerSearchView.as_view(), name="inspection-workers-search"),
    path("workers/<int:pk>/", WorkerRetrieveUpdateDestroyView.as_view(), name="inspection-worker-detail"),
    
    # Work Zones
    path("zones/", WorkZoneListCreateView.as_view(), name="inspection-zones"),
    path("zones/<int:pk>/", WorkZoneRetrieveUpdateDestroyView.as_view(), name="inspection-zone-detail"),
    
    # Attendances
    path("check-in/", CheckInView.as_view(), name="inspection-check-in"),
    path("attendance/", AttendanceByDateView.as_view(), name="attendance-by-date"),
    path("attendance/history/", AttendanceHistoryView.as_view(), name="attendance-history"),
    path("attendance/worker/<int:worker_id>/", WorkerAttendanceDetailView.as_view(), name="worker-attendance-detail"),
    path("attendances/", AttendanceListView.as_view(), name="inspection-attendances"),
    path("attendances/<int:pk>/", AttendanceRetrieveView.as_view(), name="inspection-attendance-detail"),
    path("my-attendances/", MyAttendanceListView.as_view(), name="inspection-my-attendances"),
    path("attendance-stats/", AttendanceStatsView.as_view(), name="inspection-attendance-stats"),

    # Work Schedules
    path("schedules/", WorkScheduleListCreateView.as_view(), name="inspection-schedules"),
    path("schedules/<int:pk>/", WorkScheduleRetrieveUpdateDestroyView.as_view(), name="inspection-schedule-detail"),

    # Face ID daily check in/out
    path("face-check-in-out/", FaceCheckInOutView.as_view(), name="inspection-face-check-in-out"),
    path("my-attendance-today/", MyAttendanceTodayView.as_view(), name="inspection-my-attendance-today"),
]
