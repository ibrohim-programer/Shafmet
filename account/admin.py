from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import Lavozim

User = get_user_model()

@admin.register(User)
class UserModelAdmin(admin.ModelAdmin):
    list_display = ["id","phone","full_name","role","avatar","is_active","is_staff"]
    
    def save_model(self, request, obj, form, change):
        # Hash password if it's set in plain text (e.g. on creation or when updated)
        if not change:
            obj.set_password(obj.password)
        else:
            try:
                orig_obj = User.objects.get(pk=obj.pk)
                if obj.password != orig_obj.password:
                    obj.set_password(obj.password)
            except User.DoesNotExist:
                obj.set_password(obj.password)
        super().save_model(request, obj, form, change)
    

@admin.register(Lavozim)
class LavozimAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "slug", "show_in_diagram", "is_default", "created_at"]
    list_filter = ["is_default", "show_in_diagram"]
    search_fields = ["name", "slug"]

