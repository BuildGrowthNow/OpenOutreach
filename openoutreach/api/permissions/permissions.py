# API Permissions

from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write permissions require authentication
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write permissions are only allowed to the owner of the object
        return bool(getattr(obj, 'user', None) == request.user)


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admins to edit objects.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write permissions are only allowed to admin users
        return bool(request.user and getattr(request.user, 'is_staff', False))


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners or admins to access objects.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write permissions require authentication
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Allow if user is admin
        if request.user and getattr(request.user, 'is_staff', False):
            return True
        # Allow if user is owner
        if hasattr(obj, 'user'):
            return obj.user == request.user
        # For objects without user field, check if created_by exists
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        return False