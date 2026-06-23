from rest_framework import permissions

class IsAdmin(permissions.BasePermission):
    def has_permission(self , request , view):
        return request.user.is_authenticated and request.user.role == "admin"
    
    

class IsAdminOrManager(permissions.BasePermission):
    def has_permission(self , request , view):
        return request.user.is_authenticated and request.user.role in ["admin" , 'manager']
    
    

class IsBoss(permissions.BasePermission):
    def has_permission(self , request , view):
        return request.user.is_authenticated and request.user.role == "boss"
    
    

class IsWorker(permissions.BasePermission):
    def has_permission(self , request , view):
        return request.user.is_authenticated and request.user.role == "worker"
