from .provider import (
    CourierProviderRegistrationView,
)
from .admin import (
    ApproveCourierProviderView,
    CourierProviderListView,
    CourierProviderDetailView,
)
from .rider import (
    RiderRegistrationView,
    RiderProfileView,
    update_availability_status,
)
from .consumer import (
    AddressListCreateView,
    AddressDetailView,
)

__all__ = [
    'CourierProviderRegistrationView',
    'ApproveCourierProviderView',
    'CourierProviderListView',
    'CourierProviderDetailView',
    'RiderRegistrationView',
    'RiderProfileView',
    'update_availability_status',
    'AddressListCreateView',
    'AddressDetailView',
]
