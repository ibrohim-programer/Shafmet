from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import Lavozim

User = get_user_model()

@admin.register(User)
class UserModelAdmin(admin.ModelAdmin):
    list_display = ["id","phone","full_name","role","avatar","is_active","is_staff"]
    

@admin.register(Lavozim)
class LavozimAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "slug", "show_in_diagram", "is_default", "created_at"]
    list_filter = ["is_default", "show_in_diagram"]
    search_fields = ["name", "slug"]

