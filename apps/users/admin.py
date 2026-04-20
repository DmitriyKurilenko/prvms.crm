from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Membership, RolePermission


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('email', 'username')
    ordering = ('email',)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'tenant', 'role', 'is_active', 'joined_at')
    list_filter = ('role', 'is_active')
    search_fields = ('user__email', 'tenant__name')
    raw_id_fields = ('user', 'tenant')


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'role', 'entity', 'can_view', 'can_create', 'can_update', 'can_delete', 'scope')
    list_filter = ('role', 'entity', 'scope')
    search_fields = ('tenant__name', 'tenant__slug')
    raw_id_fields = ('tenant',)
