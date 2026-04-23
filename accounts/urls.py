from django.urls import path

from accounts.views.auth import (
    UserRegistrationView, 
    ConsumerLoginView,
    CourierStaffLoginView,
    RiderLoginView,
    AdminLoginView,
    SendOTPView,
    ValidateOTPView,
    ChangePasswordAPIView,
)
from accounts.views.provider import (
    CourierProviderRegistrationView,
    CourierProviderProfileView,
    CourierProviderMeLogoView,
)
from accounts.views.admin import (
    ApproveCourierProviderView,
    CourierProviderListView,
    CourierProviderDetailView,
    ApproveCourierRiderView,
    RiderListView,
    RiderDetailView,
)
from accounts.views.rider import (
    RiderRegistrationView,
    RiderProfileView,
    update_availability_status,
)
from accounts.views.staff import (
    CourierStaffDetailAPIView,
    CourierStaffListAPIView,
    CourierStaffRegistrationView,
    CourierStaffRolePermissionUpdateAPIView,
)
from accounts.views.invitation import (
    SendInvitationView,
    InvitationListView,
    InvitationDetailView,
    InvitationTokenValidationView,
    revoke_invitation,
)
from accounts.views.consumer import (
    AddressListCreateView,
    AddressDetailView,
    ConsumerProfileUpdateView,
)

urlpatterns = [
    path('auth/register/', UserRegistrationView.as_view(), name='user-register'),
    path('auth/login/consumer/', ConsumerLoginView.as_view(), name='consumer-login'),
    path('auth/login/courier/', CourierStaffLoginView.as_view(), name='courier-login'),
    path('auth/login/rider/', RiderLoginView.as_view(), name='rider-login'),
    path('auth/login/admin/', AdminLoginView.as_view(), name='admin-login'),
    path('auth/send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('auth/validate-otp/', ValidateOTPView.as_view(), name='validate-otp'),
    path('auth/change-password/', ChangePasswordAPIView.as_view(), name='change-password'),

    # Courier Provider URLs
    path('provider/register/', CourierProviderRegistrationView.as_view(), name='provider-register'),
    path('provider/me/', CourierProviderProfileView.as_view(), name='provider-me-profile'),
    path('provider/me/logo/', CourierProviderMeLogoView.as_view(), name='provider-me-logo'),

    path('staff/', CourierStaffListAPIView.as_view(), name='staff-list'),
    path('staff/<int:pk>/', CourierStaffDetailAPIView.as_view(), name='staff-detail'),
    path('staff/<int:pk>/permissions/', CourierStaffRolePermissionUpdateAPIView.as_view(), name='staff-permissions-update'),
    path('staff/register/', CourierStaffRegistrationView.as_view(), name='staff-register'),

    # Admin endpoints for managing providers
    path('provider/', CourierProviderListView.as_view(), name='provider-list'),
    path('provider/<int:pk>/', CourierProviderDetailView.as_view(), name='provider-detail'),
    path('provider/<int:provider_id>/approve/', ApproveCourierProviderView.as_view(), name='provider-approve'),
    
    # Admin endpoints for managing riders
    path('admin/riders/', RiderListView.as_view(), name='admin-rider-list'),
    path('admin/riders/<int:pk>/', RiderDetailView.as_view(), name='admin-rider-detail'),
    path('admin/riders/<int:rider_id>/approve/', ApproveCourierRiderView.as_view(), name='admin-rider-approve'),
    
    # Provider Invitation URLs
    path('invitations/validate/', InvitationTokenValidationView.as_view(), name='invitation-validate'),
    path('invitations/send/', SendInvitationView.as_view(), name='send-invitation'),
    path('invitations/', InvitationListView.as_view(), name='invitation-list'),
    path('invitations/<int:pk>/', InvitationDetailView.as_view(), name='invitation-detail'),
    path('invitations/<int:invitation_id>/revoke/', revoke_invitation, name='revoke-invitation'),
    
    # Rider URLs
    path('riders/register/', RiderRegistrationView.as_view(), name='rider-register'),
    path('riders/profile/', RiderProfileView.as_view(), name='rider-profile'),
    path('riders/availability/', update_availability_status, name='rider-availability'),

    # Consumer URLs
    path('consumer/profile/', ConsumerProfileUpdateView.as_view(), name='consumer-profile-update'),
    path('consumer/addresses/', AddressListCreateView.as_view(), name='consumer-address-list-create'),
    path('consumer/addresses/<int:pk>/', AddressDetailView.as_view(), name='consumer-address-detail'),
]