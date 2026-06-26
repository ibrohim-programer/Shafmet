from django.urls import path

from .views import (
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
)

urlpatterns = [
    # Workers
    path("workers/create/", CreateWorkerView.as_view(), name="inspection-create-worker"),
    path("workers/", WorkerListView.as_view(), name="inspection-worker-list"),
    path("workers/<int:pk>/", WorkerRetrieveUpdateDestroyView.as_view(), name="inspection-worker-detail"),
    
    # Work Zones
    path("zones/", WorkZoneListCreateView.as_view(), name="inspection-zones"),
    path("zones/<int:pk>/", WorkZoneRetrieveUpdateDestroyView.as_view(), name="inspection-zone-detail"),
    
    # Attendances
    path("check-in/", CheckInView.as_view(), name="inspection-check-in"),
    path("attendances/", AttendanceListView.as_view(), name="inspection-attendances"),
    path("attendances/<int:pk>/", AttendanceRetrieveView.as_view(), name="inspection-attendance-detail"),
    path("my-attendances/", MyAttendanceListView.as_view(), name="inspection-my-attendances"),
    path("attendance-stats/", AttendanceStatsView.as_view(), name="inspection-attendance-stats"),
]
