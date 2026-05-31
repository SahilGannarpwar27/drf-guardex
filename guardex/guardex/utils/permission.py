from rest_framework.permissions import BasePermission
from user import choices as ROLE_CHOICES


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        # 1. Check if user is logged in securely
        if not bool(request.user and request.user.is_authenticated):
            return False
            
        # 2. Check the role safely
        return (
            hasattr(request.user, 'user_role') and 
            request.user.user_role is not None and 
            request.user.user_role.name == ROLE_CHOICES.SUPER_ADMIN
        )
        
class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        # 1. Check if user is logged in securely
        if not bool(request.user and request.user.is_authenticated):
            return False
            
        # 2. Check the role safely
        return (
            hasattr(request.user, 'user_role') and 
            request.user.user_role is not None and 
            request.user.user_role.name == ROLE_CHOICES.ADMIN
        )