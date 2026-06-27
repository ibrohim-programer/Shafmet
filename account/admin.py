from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import Department

User = get_user_model()

@admin.register(User)
class UserModelAdmin(admin.ModelAdmin):
    list_display = ["id","phone","full_name","role","avatar","is_active","is_staff"]
    

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "code"]

