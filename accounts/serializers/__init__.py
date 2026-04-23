from .auth import *
from .user import *
from .consumer import *
from .profile import *
from .provider import (
    DocumentUploadSerializer,
    CourierProviderRegistrationSerializer,
)
from .admin import (
    CourierProviderApprovalSerializer,
    CourierProviderDetailSerializer,
    CourierRiderApprovalSerializer,
    RiderAdminDetailSerializer,
)
from .rider import (
    RiderDocumentUploadSerializer,
    RiderRegistrationSerializer,
    RiderDetailSerializer,
)
from .invitation import (
    SendInvitationSerializer,
    InvitationDetailSerializer,
    InvitationListSerializer,
)
from .consumer import (
    AddressSerializer,
)

__all__ = [
    'DocumentUploadSerializer',
    'CourierProviderRegistrationSerializer',
    'CourierProviderApprovalSerializer',
    'CourierProviderDetailSerializer',
    'CourierRiderApprovalSerializer',
    'RiderAdminDetailSerializer',
    'RiderDocumentUploadSerializer',
    'RiderRegistrationSerializer',
    'RiderDetailSerializer',
    'AddressSerializer',
    'SendInvitationSerializer',
    'InvitationDetailSerializer',
    'InvitationListSerializer',
]
