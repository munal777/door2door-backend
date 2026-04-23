from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from django.utils import timezone
from django.shortcuts import get_object_or_404

from ..models import (
    Order,
    OrderTracking,
    TransportBucket,
    BucketOrder,
    BucketStop,
)
from ..serializers import (
    TransportBucketCreateSerializer,
    TransportBucketDetailSerializer,
    AddOrderToBucketSerializer,
    BucketLocationUpdateSerializer,
    BucketTrackingSerializer,
)
from ..services import BucketTrackingService
from myproject.utils import api_response
from myproject.permissions import HasShippingManagementPermission, IsCourierStaff


class TransportBucketCreateAPIView(generics.CreateAPIView):
    """
    Create a new transport bucket for grouping orders
    """
    serializer_class = TransportBucketCreateSerializer
    permission_classes = [permissions.IsAuthenticated, HasShippingManagementPermission]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            return api_response(
                is_success=False,
                error_message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        bucket = serializer.save()
        
        # Return detailed bucket info
        detail_serializer = TransportBucketDetailSerializer(bucket)
        
        return api_response(
            result=detail_serializer.data,
            is_success=True,
            status_code=status.HTTP_201_CREATED
        )


class TransportBucketListAPIView(generics.ListAPIView):
    """
    List all transport buckets for courier provider
    """
    serializer_class = TransportBucketDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsCourierStaff]
    
    def get_queryset(self):
        courier_provider = self.request.courier
        
        queryset = TransportBucket.objects.filter(
            courier_provider=courier_provider
        ).prefetch_related(
            'stops',
            'bucket_orders__order'
        ).select_related('created_by')
        
        # Filter by origin city
        origin_city = self.request.query_params.get('origin_city')
        if origin_city:
            queryset = queryset.filter(origin_city__icontains=origin_city)
        
        # Filter closed vs active
        is_closed = self.request.query_params.get('is_closed')
        if is_closed == 'true':
            queryset = queryset.exclude(closed_at__isnull=True)
        elif is_closed == 'false':
            queryset = queryset.filter(closed_at__isnull=True)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )


class TransportBucketDetailAPIView(generics.RetrieveAPIView):
    """
    Get detailed information about a specific bucket
    """
    serializer_class = TransportBucketDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsCourierStaff]
    lookup_field = 'bucket_number'
    
    def get_queryset(self):
        courier_provider = self.request.courier
        
        return TransportBucket.objects.filter(
            courier_provider=courier_provider
        ).prefetch_related(
            'stops',
            'bucket_orders__order',
            'tracking_history'
        ).select_related('created_by')
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # Include tracking history
        tracking_history = instance.tracking_history.all()
        tracking_serializer = BucketTrackingSerializer(tracking_history, many=True)
        
        response_data = serializer.data
        response_data['tracking_history'] = tracking_serializer.data
        
        return api_response(
            result=response_data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )


class AddOrdersToBucketAPIView(APIView):
    """
    Add multiple orders to a bucket
    """
    permission_classes = [permissions.IsAuthenticated, HasShippingManagementPermission]
    
    def post(self, request, bucket_number):
        courier_provider = request.courier
        
        # Get bucket
        bucket = get_object_or_404(
            TransportBucket,
            bucket_number=bucket_number,
            courier_provider=courier_provider
        )
        
        # Check bucket is not closed
        if bucket.closed_at:
            return api_response(
                is_success=False,
                error_message="Cannot add orders to a closed bucket",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate order numbers
        serializer = AddOrderToBucketSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return api_response(
                is_success=False,
                error_message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        order_numbers = serializer.validated_data['order_numbers']
        
        # Get orders
        orders = Order.objects.filter(
            order_number__in=order_numbers,
            courier_provider=courier_provider
        )
        
        # Add orders to bucket
        added_count = 0
        already_in_bucket = []
        
        for order in orders:
            # Check if order is already in any bucket
            if order.bucket_links.exists():
                already_in_bucket.append(order.order_number)
                continue
            
            BucketOrder.objects.create(
                bucket=bucket,
                order=order,
                added_by=request.user
            )
            
            # Update order status to AT_ORIGIN_HUB
            order.status = Order.OrderStatus.AT_ORIGIN_HUB
            order.save(update_fields=['status'])
            
            # Create tracking entry
            OrderTracking.objects.create(
                order=order,
                status=Order.OrderStatus.AT_ORIGIN_HUB,
                location_city=bucket.origin_city,
                remarks=f"Package received at {bucket.origin_city} sorting facility and your shipment is being prepared for dispatch to the destination hub."
            )
            
            added_count += 1

        # Return updated bucket details
        detail_serializer = TransportBucketDetailSerializer(bucket)
        
        return api_response(
            result=detail_serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )


class UpdateBucketLocationAPIView(APIView):
    """
    Update bucket location and status, which updates all orders inside
    Supports both QR code scanning and manual entry
    """
    permission_classes = [permissions.IsAuthenticated, HasShippingManagementPermission]
    
    def post(self, request, bucket_number):
        courier_provider = request.courier
        
        # Get bucket
        bucket = get_object_or_404(
            TransportBucket,
            bucket_number=bucket_number,
            courier_provider=courier_provider
        )
        
        # Validate location update data
        serializer = BucketLocationUpdateSerializer(data=request.data, context={'bucket': bucket})
        
        if not serializer.is_valid():
            return api_response(
                is_success=False,
                error_message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        action = serializer.validated_data['action']
        location_city = serializer.validated_data['location_city']
        bucket_stop_id = serializer.validated_data.get('bucket_stop_id')
        
        # Get bucket stop if provided
        bucket_stop = None
        if bucket_stop_id:
            bucket_stop = BucketStop.objects.get(id=bucket_stop_id)
        
        # Record tracking event using service
        result = BucketTrackingService.record_tracking_event(
            bucket=bucket,
            action=action,
            location_city=location_city,
            updated_by=request.user,
            bucket_stop=bucket_stop
        )

        # Handle duplicate or skipped scans
        if result.get('duplicate'):
            return api_response(
                error_message=result.get('message'),
                is_success=False,
                status_code=status.HTTP_409_CONFLICT  # More appropriate for duplicates
            )
        
        if result.get('skipped'):
            return api_response(
                error_message=result.get('message'),
                is_success=False,
                status_code=status.HTTP_200_OK  # Not an error, just no action taken
            )
        
        return api_response(
            result=result,
            is_success=True,
            status_code=status.HTTP_200_OK
        )


class CloseBucketAPIView(APIView):
    """
    Close a bucket when all deliveries are complete
    
    Permissions: Courier Staff with shipping management permission
    """
    permission_classes = [permissions.IsAuthenticated, HasShippingManagementPermission]
    
    def post(self, request, bucket_number):
        courier_provider = request.courier
        
        # Get bucket
        bucket = get_object_or_404(
            TransportBucket,
            bucket_number=bucket_number,
            courier_provider=courier_provider
        )
        
        # Check if already closed
        if bucket.closed_at:
            return api_response(
                is_success=False,
                error_message="Bucket is already closed",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Close bucket
        bucket.closed_at = timezone.now()
        bucket.save(update_fields=['closed_at'])
        
        detail_serializer = TransportBucketDetailSerializer(bucket)
        
        return api_response(
            result=detail_serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )
