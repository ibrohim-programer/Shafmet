from django.urls import path

from .views import (
    AttendanceListView,
    CheckInView,
    CreateWorkerView,
    WorkZoneListCreateView,
)

urlpatterns = [
    path("workers/create/", CreateWorkerView.as_view(), name="inspection-create-worker"),
    path("check-in/", CheckInView.as_view(), name="inspection-check-in"),
    path("zones/", WorkZoneListCreateView.as_view(), name="inspection-zones"),
    path("attendances/", AttendanceListView.as_view(), name="inspection-attendances"),
]
