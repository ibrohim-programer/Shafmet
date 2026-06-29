from django.urls import path
from .views import (
    TaskListCreateView,
    TaskRetrieveUpdateDestroyView,
    TaskStatusUpdateView,
    AssessmentListCreateView,
    AssessmentRetrieveUpdateDestroyView,
    WorkerAssessmentsListView,
)

urlpatterns = [
    # Tasks
    path("", TaskListCreateView.as_view(), name="task-list-create"),
    path("<int:pk>/", TaskRetrieveUpdateDestroyView.as_view(), name="task-detail"),
    path("<int:pk>/status/", TaskStatusUpdateView.as_view(), name="task-update-status"),

    # Assessments
    path("assessments/", AssessmentListCreateView.as_view(), name="assessment-list-create"),
    path("assessments/<int:pk>/", AssessmentRetrieveUpdateDestroyView.as_view(), name="assessment-detail"),
    path("assessments/worker/<int:worker_id>/", WorkerAssessmentsListView.as_view(), name="assessment-worker-list"),
]