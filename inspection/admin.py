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
        "worker",
        "date",
        "check_in_time",
        "check_in_success",
        "check_out_time",
        "check_out_success",
        "is_late",
    ]
    list_filter = ["check_in_success", "check_out_success", "is_late", "date"]
    search_fields = ["worker__full_name", "worker__phone"]
    readonly_fields = ["date"]
