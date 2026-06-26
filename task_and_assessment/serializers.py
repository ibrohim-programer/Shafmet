from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Task, Assessment

User = get_user_model()

class TaskSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source="assigned_to.full_name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "assigned_to",
            "assigned_to_name",
            "created_by",
            "created_by_name",
            "due_date",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def validate_assigned_to(self, value):
        if value.role != "worker":
            raise serializers.ValidationError("Vazifa faqat ishchi (worker) rolidagi foydalanuvchiga topshirilishi mumkin.")
        return value


class TaskStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ["status"]


class AssessmentSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source="worker.full_name", read_only=True)
    evaluated_by_name = serializers.CharField(source="evaluated_by.full_name", read_only=True)
    task_title = serializers.CharField(source="task.title", read_only=True)

    class Meta:
        model = Assessment
        fields = [
            "id",
            "worker",
            "worker_name",
            "evaluated_by",
            "evaluated_by_name",
            "task",
            "task_title",
            "score",
            "feedback",
            "created_at",
        ]
        read_only_fields = ["id", "evaluated_by", "created_at"]

    def validate_score(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Baholash balli 1 dan 5 gacha bo'lishi kerak.")
        return value

    def validate_worker(self, value):
        if value.role != "worker":
            raise serializers.ValidationError("Faqat ishchi (worker) roliga ega xodimlar baholanishi mumkin.")
        return value
