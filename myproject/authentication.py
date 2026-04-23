"""
Custom authentication classes for Door2Door project.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils.functional import SimpleLazyObject


class JWTAuthenticationWithCourier(JWTAuthentication):
    """
    Custom JWT authentication that attaches courier company to request.
    """
    
    def authenticate(self, request):
        """
        Authenticate the request and attach courier company.
        """
        result = super().authenticate(request)
        
        if result is not None:
            user, token = result
            # Attach courier to request using lazy evaluation
            request.courier = SimpleLazyObject(lambda: self._get_courier_company(user))
        else:
            # No authentication, set courier to None
            request.courier = None
        
        return result
    
    def _get_courier_company(self, user):
        """
        Get the courier company associated with the authenticated user.
        """
        if not user or not user.is_authenticated:
            return None
        
        # Check if user is courier staff
        if user.user_type == 'courier_staff' and hasattr(user, 'courier_staff_profile'):
            return user.courier_staff_profile.company
        
        # Check if user is a rider
        if user.user_type == 'rider' and hasattr(user, 'rider_profile'):
            return user.rider_profile.company
        
        return None
