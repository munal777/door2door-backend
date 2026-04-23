from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from myproject.utils import api_response

from accounts.models.rider import Rider
from accounts.serializers.rider import (
    RiderRegistrationSerializer,
    RiderDetailSerializer,
)
from accounts.parsers import NestedMultipartParser

class RiderRegistrationView(generics.CreateAPIView):
    """
    API endpoint for rider registration with invitation token.
    Riders must provide a valid invitation token from their courier company.
    """
    serializer_class = RiderRegistrationSerializer
    permission_classes = [AllowAny]
    parser_classes = [NestedMultipartParser]

    def create(self, request, *args, **kwargs):
        """Handle rider registration"""
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                rider = serializer.save()
                return api_response(
                    result={
                        'message': 'Rider registration successful. Your account is pending document verification.'
                    },
                    is_success=True,
                    status_code=status.HTTP_201_CREATED
                )
            except Exception as e:
                return api_response(
                    error_message=f'Registration failed: {str(e)}',
                    is_success=False,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        
        return api_response(
            error_message=serializer.errors,
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class RiderProfileView(generics.RetrieveUpdateAPIView):
    """
    API endpoint for rider to view and update their profile.
    """
    serializer_class = RiderDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """Get the rider profile for the authenticated user"""
        try:
            return Rider.objects.select_related('user', 'company').get(
                user=self.request.user
            )
        except Rider.DoesNotExist:
            return None

    def get(self, request, *args, **kwargs):
        """Retrieve rider profile"""
        rider = self.get_object()
        if not rider:
            return api_response(
                error_message='Rider profile not found',
                is_success=False,
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(rider)
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )

    def update(self, request, *args, **kwargs):
        """Update rider profile"""
        rider = self.get_object()
        if not rider:
            return api_response(
                error_message='Rider profile not found',
                is_success=False,
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Only allow updating certain fields
        allowed_fields = [
            'emergency_contact_name', 'emergency_contact_phone',
            'vehicle_model', 'vehicle_color'
        ]
        
        data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        serializer = self.get_serializer(rider, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return api_response(
                result=serializer.data,
                is_success=True,
                status_code=status.HTTP_200_OK
            )
        
        return api_response(
            error_message=serializer.errors,
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_availability_status(request):
    """
    Update rider's availability status (available/busy/offline).
    """
    if request.user.user_type != 'rider':
        return api_response(
            error_message='Only riders can update availability status',
            is_success=False,
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        rider = Rider.objects.get(user=request.user)
    except Rider.DoesNotExist:
        return api_response(
            error_message='Rider profile not found',
            is_success=False,
            status_code=status.HTTP_404_NOT_FOUND
        )
    
    new_status = request.data.get('status')
    
    if new_status not in dict(Rider.AvailabilityStatus.choices):
        return api_response(
            error_message='Invalid status',
            result={'valid_statuses': list(dict(Rider.AvailabilityStatus.choices).keys())},
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Only allow availability changes if rider is operational
    if rider.operational_status != Rider.OperationalStatus.ACTIVE:
        return api_response(
            error_message='Cannot update availability. Your account is not active.',
            result={'operational_status': rider.operational_status},
            is_success=False,
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    rider.availability_status = new_status
    rider.save(update_fields=['availability_status', 'updated_at'])
    
    return api_response(
        result={
            'message': 'Availability status updated successfully',
            'status': rider.availability_status
        },
        is_success=True,
        status_code=status.HTTP_200_OK
    )