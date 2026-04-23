from rest_framework import permissions
from accounts.models import User, CourierStaff

class IsSystemAdmin(permissions.BasePermission):
    """Custom permission for System Admin only"""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            request.user.user_type in [User.UserType.SYSTEM_ADMIN, User.UserType.SYSTEM_SUPER_ADMIN]
        )
    
class IsCourierAdmin(permissions.BasePermission):
    """
    Permission check for courier provider admin users.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            courier_staff = CourierStaff.objects.filter(
                user=request.user,
                role='admin'
            ).first()
            
            # User must be an admin (views will filter by their specific courier_provider)
            return courier_staff is not None
        except Exception:
            return False
    
    message = 'You must be a courier admin to perform this action.'



class IsCourierStaff(permissions.BasePermission):
    """Custom permission for Courier Staff"""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            hasattr(request.user, 'courier_staff_profile')
        )


class HasOrderManagementPermission(permissions.BasePermission):
    """
    Permission for staff members who can manage orders.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            if not hasattr(request.user, 'courier_staff_profile'):
                return False
            
            staff = request.user.courier_staff_profile
            
            # Check if staff is active
            if not staff.is_active:
                return False
            
            # Admins have all permissions, or check specific permission
            return staff.is_admin or staff.can_manage_orders
            
        except Exception:
            return False
    
    message = 'You do not have permission to manage orders.'


class HasInvitationManagementPermission(permissions.BasePermission):
    """
    Permission for staff members who can manage rider invitations.
    Admins always pass. Operations staff need can_manage_invitations=True.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        try:
            if not hasattr(request.user, 'courier_staff_profile'):
                return False

            staff = request.user.courier_staff_profile

            if not staff.is_active:
                return False

            return staff.is_admin or staff.can_manage_invitations

        except Exception:
            return False

    message = 'You do not have permission to manage invitations.'


class HasShippingManagementPermission(permissions.BasePermission):
    """
    Permission for staff members who can manage shippings / transport buckets.
    Admins always pass. Operations staff need can_manage_shippings=True.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        try:
            if not hasattr(request.user, 'courier_staff_profile'):
                return False

            staff = request.user.courier_staff_profile

            if not staff.is_active:
                return False

            return staff.is_admin or staff.can_manage_shippings

        except Exception:
            return False

    message = 'You do not have permission to manage shippings.'


class HasRiderManagementPermission(permissions.BasePermission):
    """
    Permission for staff members who can manage rider.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        try:
            if not hasattr(request.user, 'courier_staff_profile'):
                return False

            staff = request.user.courier_staff_profile

            if not staff.is_active:
                return False

            return staff.is_admin or staff.can_manage_riders

        except Exception:
            return False

    message = 'You do not have permission to manage riders.'


class IsRiderUser(permissions.BasePermission):
    """
    Permission for authenticated rider users only.
    """

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type == User.UserType.RIDER and
            hasattr(request.user, 'rider_profile')
        )

    message = 'Only rider accounts can perform this action.'


class CanViewOrManageCourierSettings(permissions.BasePermission):
    """
    Any active courier staff can view settings.
    Only admins or staff with can_manage_settings can modify settings.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        try:
            if not hasattr(request.user, 'courier_staff_profile'):
                return False

            staff = request.user.courier_staff_profile
            if not staff.is_active:
                return False

            if request.method in permissions.SAFE_METHODS:
                return True

            return staff.is_admin or staff.can_manage_settings
        except Exception:
            return False

    message = 'You do not have permission to manage courier settings.'

class IsConsumer(permissions.BasePermission):
    """
    Permission for authenticated consumer users only.
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type == 'consumer'
        )

    message = 'Only consumer accounts can perform this action.'