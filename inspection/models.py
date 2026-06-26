from django.db import models
from django.conf import settings


class FaceProfile(models.Model):
    """Ishchining yuz profili — ro'yxatdan o'tkazilganda encoding saqlanadi."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="face_profile",
        verbose_name="Foydalanuvchi",
    )
    encoding = models.JSONField("Yuz encoding (128 float)")
    photo = models.ImageField("Yuz rasmi", upload_to="faces/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Yuz profili"
        verbose_name_plural = "Yuz profillari"

    def __str__(self):
        return f"FaceProfile: {self.user.full_name}"


class WorkZone(models.Model):
    """Ish hududi — geofencing uchun markaz nuqtasi va radius."""
    name = models.CharField("Hudud nomi", max_length=255)
    latitude = models.FloatField("Kenglik (latitude)")
    longitude = models.FloatField("Uzunlik (longitude)")
    radius_meters = models.PositiveIntegerField("Radius (metr)", default=100)
    is_active = models.BooleanField("Faolmi", default=True)

    class Meta:
        verbose_name = "Ish hududi"
        verbose_name_plural = "Ish hududlari"

    def __str__(self):
        return self.name


class AttendanceType(models.TextChoices):
    IN = "in", "Kirish (In)"
    OUT = "out", "Chiqish (Out)"


class Attendance(models.Model):
    """Davomat yozuvi — har bir check-in/out urinishi (muvaffaqiyatli yoki yo'q)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendances",
        verbose_name="Foydalanuvchi",
    )
    attendance_type = models.CharField(
        "Davomat turi",
        max_length=10,
        choices=AttendanceType.choices,
        default=AttendanceType.IN,
    )
    latitude = models.FloatField("Kenglik")
    longitude = models.FloatField("Uzunlik")
    distance_meters = models.FloatField("Masofa (metr)")
    face_verified = models.BooleanField("Yuz tasdiqlandi", default=False)
    location_verified = models.BooleanField("Joylashuv tasdiqlandi", default=False)
    is_success = models.BooleanField("Muvaffaqiyatli", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Davomat"
        verbose_name_plural = "Davomatlar"
        ordering = ["-created_at"]

    def __str__(self):
        status = "✓" if self.is_success else "✗"
        return f"{status} {self.user.full_name} ({self.get_attendance_type_display()}) — {self.created_at:%Y-%m-%d %H:%M}"
