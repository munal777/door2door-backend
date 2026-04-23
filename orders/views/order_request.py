from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from django.utils import timezone
from django.db import transaction

from ..models import Order, OrderRequest, OrderRequestCourierResponse, OrderTracking
from ..serializers import (
    OrderRequestCreateSerializer,
    OrderRequestHistorySerializer,
    OrderRequestDetailSerializer,
    NearbyOrderRequestListSerializer,
    NearbyOrderRequestDetailSerializer,
    NearbyOrderRequestActionSerializer,
)
from ..services import OrderRequestVisibilityService
from notifications.tasks import send_order_accepted_notification
from myproject.utils import api_response
from myproject.permissions import HasOrderManagementPermission, IsConsumer


class OrderRequestCreateAPIView(generics.CreateAPIView):
    """
    Consumer submits an online delivery order request.
    """
    serializer_class = OrderRequestCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsConsumer]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                is_success=False,
                error_message={
                    'message': 'Order request submission failed.',
                    'errors': serializer.errors,
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return api_response(
            result={
                'message': 'Order request submitted successfully.',
            },
            is_success=True,
            status_code=status.HTTP_201_CREATED,
        )


class ConsumerOrderRequestHistoryAPIView(generics.ListAPIView):
    """
    Consumer lists their own order requests.
    """
    serializer_class = OrderRequestHistorySerializer
    permission_classes = [permissions.IsAuthenticated, IsConsumer]

    def get_queryset(self):
        queryset = OrderRequest.objects.filter(consumer=self.request.user).select_related('order')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return api_response(result=serializer.data, is_success=True, status_code=status.HTTP_200_OK)


class ConsumerOrderRequestDetailAPIView(generics.RetrieveAPIView):
    """
    Consumer views details of a specific order request.
    GET /orders/requests/<request_number>/

    If the request was accepted, the response includes the resulting order_number.
    """
    serializer_class = OrderRequestDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsConsumer]
    lookup_field = 'request_number'

    def get_queryset(self):
        return OrderRequest.objects.filter(consumer=self.request.user).select_related('accepted_by', 'order')

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return api_response(
            result=self.get_serializer(instance).data,
            is_success=True,
            status_code=status.HTTP_200_OK,
        )


class CancelOrderRequestAPIView(APIView):
    """
    Consumer cancels a pending order request.
    """
    permission_classes = [permissions.IsAuthenticated, IsConsumer]

    def patch(self, request, request_number):
        try:
            order_request = OrderRequest.objects.get(
                request_number=request_number,
                consumer=request.user,
            )
        except OrderRequest.DoesNotExist:
            return api_response(
                is_success=False,
                error_message="Order request not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if order_request.status != OrderRequest.RequestStatus.PENDING:
            return api_response(
                is_success=False,
                error_message=(
                    f"Cannot cancel a request with status '{order_request.get_status_display()}'. "
                    "Only pending requests can be cancelled."
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        order_request.status = OrderRequest.RequestStatus.REJECTED
        order_request.rejection_reason = "Cancelled by consumer."
        order_request.responded_at = timezone.now()
        order_request.save(update_fields=['status', 'rejection_reason', 'responded_at'])

        return api_response(
            result=OrderRequestDetailSerializer(order_request).data,
            is_success=True,
            status_code=status.HTTP_200_OK,
        )


class NearbyOrderRequestListAPIView(generics.ListAPIView):
    """
    Courier staff lists nearby online order requests by exact pickup city/state.
    Only active pending requests (not expired) are returned.
    """
    serializer_class = NearbyOrderRequestListSerializer
    permission_classes = [permissions.IsAuthenticated, HasOrderManagementPermission]

    def get_queryset(self):
        return OrderRequestVisibilityService.nearby_pending_requests_for_courier(
            self.request.courier
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK,
        )


class NearbyOrderRequestDetailAPIView(generics.RetrieveAPIView):
    """
    Courier staff views a specific nearby online order request.
    Request must be pending, not expired, and in same pickup city/state.
    """
    serializer_class = NearbyOrderRequestDetailSerializer
    permission_classes = [permissions.IsAuthenticated, HasOrderManagementPermission]
    lookup_field = 'request_number'

    def get_queryset(self):
        return OrderRequestVisibilityService.nearby_pending_requests_for_courier(
            self.request.courier
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return api_response(
            result=self.get_serializer(instance).data,
            is_success=True,
            status_code=status.HTTP_200_OK,
        )


class NearbyOrderRequestActionAPIView(APIView):
    """
    Courier action on nearby order requests.
    """
    permission_classes = [permissions.IsAuthenticated, HasOrderManagementPermission]

    @staticmethod
    def _send_order_accepted_push_async(user_id: int, order_number: str):
        transaction.on_commit(
            lambda: send_order_accepted_notification.delay(user_id, order_number)
        )

    @transaction.atomic
    def post(self, request, request_number):
        courier_provider = request.courier
        serializer = NearbyOrderRequestActionSerializer(data=request.data)

        if not serializer.is_valid():
            return api_response(
                is_success=False,
                error_message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not courier_provider:
            return api_response(
                is_success=False,
                error_message='Courier provider profile not found for this user.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        action = serializer.validated_data['action']
        reason = serializer.validated_data.get('reason', '').strip()

        now = OrderRequestVisibilityService.expire_stale_pending_requests()

        # Lock the order request row to avoid concurrent accepts.
        try:
            order_request = OrderRequest.objects.select_for_update().get(
                request_number=request_number,
            )
        except OrderRequest.DoesNotExist:
            return api_response(
                is_success=False,
                error_message='Order request not found.',
                status_code=status.HTTP_404_NOT_FOUND,
            )

        in_nearby_scope = OrderRequestVisibilityService.is_request_in_courier_nearby_scope(
            order_request=order_request,
            courier_provider=courier_provider,
        )

        if action == NearbyOrderRequestActionSerializer.ACTION_ACCEPT:
            if not in_nearby_scope:
                return api_response(
                    is_success=False,
                    error_message='This request is not available for acceptance for your location or has already been handled.',
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            if order_request.status != OrderRequest.RequestStatus.PENDING or order_request.expires_at <= now:
                return api_response(
                    is_success=False,
                    error_message='This request is no longer available for acceptance.',
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            order_request.status = OrderRequest.RequestStatus.ACCEPTED
            order_request.accepted_by = courier_provider
            order_request.rejection_reason = ''
            accepted_at = timezone.now()
            order_request.responded_at = accepted_at
            order_request.save(update_fields=['status', 'accepted_by', 'rejection_reason', 'responded_at'])

            # Create operational order automatically for accepted online request
            order = getattr(order_request, 'order', None)
            if not order:
                estimated_delivery_hours = (
                    24
                    if order_request.service_type == Order.ServiceType.EXPRESS
                    else 48
                )

                order = Order.objects.create(
                    order_type=Order.OrderType.ONLINE,
                    order_request=order_request,
                    consumer=order_request.consumer,
                    sender_name=order_request.pickup_name,
                    sender_phone=order_request.pickup_phone,
                    sender_email='',
                    sender_address=order_request.pickup_address,
                    sender_city=order_request.pickup_city,
                    sender_state=order_request.pickup_state,
                    sender_latitude=order_request.pickup_latitude,
                    sender_longitude=order_request.pickup_longitude,
                    receiver_name=order_request.delivery_name,
                    receiver_phone=order_request.delivery_phone,
                    receiver_email='',
                    receiver_address=order_request.delivery_address,
                    receiver_city=order_request.delivery_city,
                    receiver_state=order_request.delivery_state,
                    receiver_latitude=order_request.delivery_latitude,
                    receiver_longitude=order_request.delivery_longitude,
                    package_type=order_request.package_type,
                    weight=order_request.weight,
                    total_quantity=order_request.total_quantity,
                    length=order_request.length,
                    width=order_request.width,
                    height=order_request.height,
                    package_description=order_request.package_description,
                    service_type=order_request.service_type,
                    estimated_delivery_hours=estimated_delivery_hours,
                    total_price=order_request.estimated_price,
                    payment_method=order_request.payment_method,
                    payment_status=Order.PaymentStatus.PENDING,
                    courier_provider=courier_provider,
                    status=Order.OrderStatus.CONFIRMED,
                    confirmed_at=accepted_at,
                    created_by=request.user,
                )

                OrderTracking.objects.create(
                    order=order,
                    status=Order.OrderStatus.CONFIRMED,
                    location_city=order.sender_city,
                    remarks=(
                        f"Your order request has been accepted by {courier_provider.name}. "
                        f"We have started processing your shipment from {order.sender_city}."
                    ),
                )

            self._send_order_accepted_push_async(
                user_id=order_request.consumer_id,
                order_number=order.order_number,
            )

            return api_response(
                result={
                    'message': 'Order request accepted successfully.',
                    'request_number': order_request.request_number,
                    'status': order_request.status,
                    'accepted_by': courier_provider.name,
                    'order_number': order.order_number,
                },
                is_success=True,
                status_code=status.HTTP_200_OK,
            )

        # Decline / Ignore are personal to courier; do not change global request status.
        if not in_nearby_scope:
            return api_response(
                is_success=False,
                error_message='This request is not available for your location or has already been handled.',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        response_type = (
            OrderRequestCourierResponse.ResponseType.DECLINED
            if action == NearbyOrderRequestActionSerializer.ACTION_DECLINE
            else OrderRequestCourierResponse.ResponseType.IGNORED
        )

        OrderRequestCourierResponse.objects.update_or_create(
            order_request=order_request,
            courier_provider=courier_provider,
            defaults={
                'response_type': response_type,
                'reason': reason,
            },
        )

        return api_response(
            result={
                'message': f"Order request {action}d for your courier account.",
                'request_number': order_request.request_number,
                'action': action,
            },
            is_success=True,
            status_code=status.HTTP_200_OK,
        )
