from django.db import models
from django.conf import settings

class TaskStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"

class Task(models.Model):
    title = models.CharField("Sarlavha", max_length=255)
    description = models.TextField("Tavsif", blank=True, null=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assigned_tasks",
        verbose_name="Topshirilgan xodim"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_tasks",
        verbose_name="Yaratuvchi"
    )
    due_date = models.DateTimeField("Muddati", blank=True, null=True)
    status = models.CharField(
        "Holati",
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Vazifa"
        verbose_name_plural = "Vazifalar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Assessment(models.Model):
    worker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assessments",
        verbose_name="Baholangan xodim"
    )
    evaluated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="given_assessments",
        verbose_name="Baholagan rahbar"
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="assessments",
        verbose_name="Vazifa"
    )
    score = models.PositiveIntegerField("Baholash balli (1-5)", default=5)
    feedback = models.TextField("Fikr-mulohaza", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Baholash"
        verbose_name_plural = "Baholashlar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.worker.full_name} - {self.score} ball"
