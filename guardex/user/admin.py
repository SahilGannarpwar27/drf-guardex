from django.contrib import admin
from .models import User, UserRole, Organization

# Register your models here.
# admin.site.register(User)
admin.site.register(UserRole)
admin.site.register(Organization)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'email', 'first_name', 'last_name', 'user_role', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'user_role')
    search_fields = ('phone_number', 'email', 'first_name', 'last_name')
    ordering = ('phone_number',)