from django.contrib import admin

from .models import Attendance, FaceProfile, WorkZone


@admin.register(FaceProfile)
class FaceProfileAdmin(admin.ModelAdmin):
    list_display = ["id","user", "created_at"]
    search_fields = ["user__full_name", "user__phone"]
    readonly_fields = ["encoding", "created_at"]


@admin.register(WorkZone)
class WorkZoneAdmin(admin.ModelAdmin):
    list_display = ["id","name", "latitude", "longitude", "radius_meters", "is_active"]
    list_filter = ["is_active"]


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "face_verified",
        "location_verified",
        "is_success",
        "distance_meters",
        "created_at",
    ]
    list_filter = ["is_success", "face_verified", "location_verified"]
    search_fields = ["user__full_name", "user__phone"]
    readonly_fields = ["created_at"]
