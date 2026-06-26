from django.db import models
from django.conf import settings

class FCMDevice(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fcm_devices",
        verbose_name="Foydalanuvchi"
    )
    device_token = models.TextField("Device Token", unique=True)
    device_type = models.CharField("Qurilma turi (android/ios/web)", max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FCM Qurilma"
        verbose_name_plural = "FCM Qurilmalar"

    def __str__(self):
        return f"{self.user.full_name} - {self.device_type or 'Qurilma'}"

