from rest_framework import status, permissions
from rest_framework.views import APIView

from ..models import OrderTracking
from ..serializers import PublicOrderTrackingSerializer
from myproject.utils import api_response


class PublicOrderTrackingAPIView(APIView):
    """
    Public API for customers to track their orders by order number
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, order_number):
        # Get all tracking history for the order
        order_tracking = OrderTracking.objects.filter(
            order__order_number=order_number
        ).order_by('-created_at')
        
        if not order_tracking.exists():
            return api_response(
                is_success=False,
                error_message="Order not found. Please check your order number and try again.",
                status_code=status.HTTP_404_NOT_FOUND
            )

        serializer = PublicOrderTrackingSerializer(order_tracking, many=True)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )
