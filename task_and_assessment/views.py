from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdminOrManager, IsWorker, IsBoss
from .models import Task, Assessment
from .serializers import (
    TaskSerializer,
    TaskStatusUpdateSerializer,
    AssessmentSerializer,
)

# ─────────────────────────────────────────────
# Task Views
# ─────────────────────────────────────────────

@extend_schema(
    tags=["Tasks"],
    summary="Vazifalar ro'yxati va yangi vazifa yaratish (Admin/Manager/Boss)",
)
class TaskListCreateView(generics.ListCreateAPIView):
    queryset = Task.objects.select_related("assigned_to", "created_by").all()
    serializer_class = TaskSerializer
    permission_classes = [IsAdminOrManager | IsBoss]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@extend_schema(
    tags=["Tasks"],
    summary="Vazifa tafsilotlari, tahrirlash va o'chirish (Admin/Manager/Boss)",
)
class TaskRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Task.objects.select_related("assigned_to", "created_by").all()
    serializer_class = TaskSerializer
    permission_classes = [IsAdminOrManager | IsBoss]


@extend_schema(
    tags=["Tasks"],
    summary="Faqat o'ziga tegishli vazifalar ro'yxatini ko'rish (Faqat Worker)",
)
class MyTasksListView(generics.ListAPIView):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Task.objects.filter(assigned_to=self.request.user).select_related("assigned_to", "created_by")


@extend_schema(
    tags=["Tasks"],
    summary="Vazifa holatini yangilash (Faqat topshiriq egasi bo'lgan Worker)",
)
class TaskStatusUpdateView(generics.UpdateAPIView):
    serializer_class = TaskStatusUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Task.objects.filter(assigned_to=self.request.user)

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


# ─────────────────────────────────────────────
# Assessment Views
# ─────────────────────────────────────────────

@extend_schema(
    tags=["Assessments"],
    summary="Baholashlar ro'yxati va yangi baho qo'shish (Admin/Manager/Boss)",
)
class AssessmentListCreateView(generics.ListCreateAPIView):
    queryset = Assessment.objects.select_related("worker", "evaluated_by", "task").all()
    serializer_class = AssessmentSerializer
    permission_classes = [IsAdminOrManager | IsBoss]

    def perform_create(self, serializer):
        serializer.save(evaluated_by=self.request.user)


@extend_schema(
    tags=["Assessments"],
    summary="Bahoni ko'rish, tahrirlash va o'chirish (Admin/Manager/Boss)",
)
class AssessmentRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Assessment.objects.select_related("worker", "evaluated_by", "task").all()
    serializer_class = AssessmentSerializer
    permission_classes = [IsAdminOrManager | IsBoss]


@extend_schema(
    tags=["Assessments"],
    summary="Ma'lum bir xodimning barcha baholari (Admin/Manager/Boss/Worker o'zi uchun)",
)
class WorkerAssessmentsListView(generics.ListAPIView):
    serializer_class = AssessmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        worker_id = self.kwargs.get("worker_id")
        user = self.request.user
        
        # Agar user xodim bo'lsa va boshqa xodimning baholarini ko'rmoqchi bo'lsa rad etiladi
        if user.role == "worker" and user.id != worker_id:
            raise permissions.exceptions.PermissionDenied("Siz faqat o'zingizning baholaringizni ko'ra olasiz.")
            
        return Assessment.objects.filter(worker_id=worker_id).select_related("worker", "evaluated_by", "task")
