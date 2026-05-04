from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Q

from ..models import Order, OrderTracking
from ..serializers import (
    ManualOrderCreateSerializer,
    ManualOrderUpdateSerializer,
    OrderDetailSerializer,
    OrderTrackingSerializer,
    OrderListSerializer,
)
from myproject.utils import api_response
from myproject.permissions import HasOrderManagementPermission, IsCourierStaff
from ..paginations import StandardResultsSetPagination


class ManualOrderCreateAPIView(generics.CreateAPIView):
    """
    Create manual order for walk-in customers at courier office
    """
    serializer_class = ManualOrderCreateSerializer
    permission_classes = [permissions.IsAuthenticated, HasOrderManagementPermission]
    
    def create(self, request, *args, **kwargs):
        
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            return api_response(
                is_success=False,
                error_message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        order = serializer.save()
        order.confirmed_at = timezone.now()
        order.save()
        
        # Return detailed response
        detail_serializer = OrderDetailSerializer(order)
        
        return api_response(
            result=detail_serializer.data,
            is_success=True,
            status_code=status.HTTP_201_CREATED
        )

class OrderListAPIView(generics.ListAPIView):
    """
    List all orders for the courier provider
    """
    serializer_class = OrderListSerializer
    permission_classes = [permissions.IsAuthenticated, IsCourierStaff]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        courier_provider = self.request.courier
        
        # Base queryset - only manual orders for this courier
        queryset = Order.objects.filter(
            courier_provider=courier_provider,
        ).select_related(
            'courier_provider',
            'created_by'
        )
        
        # Filter by status
        order_status = self.request.query_params.get('status')
        if order_status:
            queryset = queryset.filter(status=order_status)
        
        # Filter by payment status
        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        
        # Search functionality
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search) |
                Q(sender_name__icontains=search) |
                Q(sender_phone__icontains=search) |
                Q(receiver_name__icontains=search) |
                Q(receiver_phone__icontains=search)
            )
        
        # Date range filter
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            # Get the paginated response data
            paginated_response = self.paginator.get_paginated_response(serializer.data)
            # Wrap in custom api_response format
            return api_response(
                result=paginated_response.data,
                is_success=True,
                status_code=status.HTTP_200_OK
            )
        
        # Non-paginated response
        serializer = self.get_serializer(queryset, many=True)
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )


class OrderDetailAPIView(generics.RetrieveAPIView):
    """
    Get detailed information about a specific order
    """
    serializer_class = OrderDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsCourierStaff]
    lookup_field = 'order_number'
    
    def get_queryset(self):
        courier_provider = self.request.courier
        
        return Order.objects.filter(
            courier_provider=courier_provider,
        ).select_related(
            'courier_provider',
            'created_by'
        )
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # Include tracking history
        tracking_history = OrderTracking.objects.filter(
            order=instance
        ).order_by('-created_at')
        tracking_serializer = OrderTrackingSerializer(tracking_history, many=True)
        
        response_data = serializer.data
        response_data['tracking_history'] = tracking_serializer.data
        
        return api_response(
            result=response_data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )


class UpdateOrderPaymentStatusAPIView(APIView):
    """
    Update payment status of an order
    """
    permission_classes = [permissions.IsAuthenticated, HasOrderManagementPermission]
    
    def patch(self, request, order_number):
        courier_provider = request.courier
        
        # Get order
        try:
            order = Order.objects.get(
                order_number=order_number,
                courier_provider=courier_provider
            )
        except Order.DoesNotExist:
            return api_response(
                is_success=False,
                error_message="Order not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Update payment status
        payment_status = request.data.get('payment_status')
        
        if payment_status not in [status[0] for status in Order.PaymentStatus.choices]:
            return api_response(
                is_success=False,
                error_message=f"Invalid payment status. Must be one of: {', '.join([s[0] for s in Order.PaymentStatus.choices])}",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        order.payment_status = payment_status
        order.save()
        
        # Add tracking entry with customer-friendly message
        payment_messages = {
            Order.PaymentStatus.PAID: "Your payment has been confirmed. Thank you for your payment!",
            Order.PaymentStatus.PENDING: "Payment is pending for this order.",
            Order.PaymentStatus.FAILED: "Payment attempt failed. Please retry the payment.",
            Order.PaymentStatus.REFUNDED: "Your payment has been refunded."
        }
        
        OrderTracking.objects.create(
            order=order,
            status=order.status,
            location_city=order.sender_city,
            remarks=payment_messages.get(payment_status, f"Payment status updated to {order.get_payment_status_display()}."),
        )
        
        serializer = OrderDetailSerializer(order)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )


class ManualOrderUpdateAPIView(APIView):
    """
    Manually update order status, payment status, or parcel details.

    Designed for CRM staff operations: walk-in corrections, exception handling,
    and status overrides. All changes are audit-trailed via OrderTracking.

    PATCH /orders/{order_number}/update/
    """
    permission_classes = [permissions.IsAuthenticated, HasOrderManagementPermission]

    def patch(self, request, order_number):
        courier_provider = request.courier

        try:
            order = Order.objects.get(
                order_number=order_number,
                courier_provider=courier_provider
            )
        except Order.DoesNotExist:
            return api_response(
                is_success=False,
                error_message="Order not found.",
                status_code=status.HTTP_404_NOT_FOUND
            )

        serializer = ManualOrderUpdateSerializer(data=request.data)

        if not serializer.is_valid():
            return api_response(
                is_success=False,
                error_message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        updated_order = serializer.update(order, serializer.validated_data)

        # Return full detail with refreshed tracking history
        detail_serializer = OrderDetailSerializer(updated_order)
        tracking_history = OrderTracking.objects.filter(
            order=updated_order
        ).order_by('-created_at')
        tracking_serializer = OrderTrackingSerializer(tracking_history, many=True)

        response_data = detail_serializer.data
        response_data['tracking_history'] = tracking_serializer.data

        return api_response(
            result=response_data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )
