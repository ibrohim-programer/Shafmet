from django.contrib import admin
from django.contrib.auth import get_user_model

User = get_user_model()

@admin.register(User)
class UserModelAdmin(admin.ModelAdmin):
    list_display = ["id","phone","full_name","role","avatar","is_active","is_staff"]
    
