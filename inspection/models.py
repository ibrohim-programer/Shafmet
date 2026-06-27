from django.db import models
from django.conf import settings
from django.utils import timezone


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

    def clean(self):
        super().clean()
        
        needs_encoding = False
        if not self.encoding:
            needs_encoding = True
        elif self.pk:
            try:
                orig = FaceProfile.objects.get(pk=self.pk)
                if orig.photo != self.photo and orig.encoding == self.encoding:
                    needs_encoding = True
            except FaceProfile.DoesNotExist:
                pass

        if needs_encoding and self.photo:
            try:
                self.photo.seek(0)
            except Exception:
                pass
            from .services import get_face_encoding
            encoding = get_face_encoding(self.photo)
            if not encoding:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    {"photo": "Rasmda yuz topilmadi. Iltimos, aniq yuz rasmi yuklang."}
                )
            self.encoding = encoding

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


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
    ip_address = models.CharField("IP Manzil", max_length=45, blank=True, null=True)
    attempts = models.PositiveIntegerField("Urinishlar soni", default=1)
    is_late = models.BooleanField("Kechikdimi", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Davomat"
        verbose_name_plural = "Davomatlar"
        ordering = ["-created_at"]

    def __str__(self):
        status = "✓" if self.is_success else "✗"
        return f"{status} {self.user.full_name} ({self.get_attendance_type_display()}) — {self.created_at:%Y-%m-%d %H:%M}"


class WorkSchedule(models.Model):
    """Ish vaqti jadvali — bo'limlar uchun ish boshlanish va tugash vaqti."""
    departments = models.ManyToManyField('account.Department', related_name='work_schedules', verbose_name="Bo'limlar")
    start_time = models.TimeField("Ish boshlanish vaqti")
    end_time = models.TimeField("Ish tugash vaqti")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_schedules",
        verbose_name="Yaratuvchi"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ish vaqti jadvali"
        verbose_name_plural = "Ish vaqti jadvallari"

    def __str__(self):
        return f"Schedule ({self.start_time:%H:%M} - {self.end_time:%H:%M})"


class DailyAttendance(models.Model):
    """Xodimning kunlik umumiy davomat yozuvi (kirish va chiqish vaqti)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_attendances",
        verbose_name="Foydalanuvchi"
    )
    date = models.DateField("Sana", default=timezone.now)
    check_in_time = models.DateTimeField("Kirish vaqti", null=True, blank=True)
    check_out_time = models.DateTimeField("Chiqish vaqti", null=True, blank=True)
    is_late = models.BooleanField("Kechikdimi", default=False)

    class Meta:
        verbose_name = "Kunlik davomat"
        verbose_name_plural = "Kunlik davomatlar"
        unique_together = ("user", "date")

    def __str__(self):
        return f"{self.user.full_name} - {self.date} (In: {self.check_in_time}, Out: {self.check_out_time})"

    @property
    def worked_duration(self):
        if self.check_in_time and self.check_out_time:
            return self.check_out_time - self.check_in_time
        elif self.check_in_time and not self.check_out_time:
            return timezone.now() - self.check_in_time
        return None
