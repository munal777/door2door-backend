from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied

from accounts.models import Rider
from myproject.permissions import IsRiderUser
from myproject.utils import api_response
from notifications.services import PushNotificationService
from orders.models import Order, OrderTracking
from riders.models import RiderLocationUpdate, RiderOrderAssignment

from riders.serializers.app import (
    RiderAppAvailabilityUpdateSerializer,
    RiderAppProfileSerializer,
    RiderAssignedOrderDetailSerializer,
    RiderAssignedOrderListSerializer,
    RiderLiveLocationUpdateSerializer,
    RiderLocationUpdateResponseSerializer,
    RiderOrderStatusUpdateSerializer,
)


def _get_authenticated_rider(user):
	if not user.is_authenticated or user.user_type != 'rider' or not hasattr(user, 'rider_profile'):
		raise PermissionDenied('Only riders can access rider app order APIs.')
	return user.rider_profile


class RiderAppProfileAPIView(APIView):
	"""
	Rider app profile endpoint for authenticated rider users.
	"""

	permission_classes = [permissions.IsAuthenticated, IsRiderUser]

	def get(self, request):
		rider = _get_authenticated_rider(request.user)
		serializer = RiderAppProfileSerializer(rider)
		return api_response(result=serializer.data, is_success=True, status_code=status.HTTP_200_OK)

	def patch(self, request):
		rider = _get_authenticated_rider(request.user)
		allowed_fields = {
			'emergency_contact_name',
			'emergency_contact_phone',
			'vehicle_model',
			'vehicle_color',
		}
		payload = {key: value for key, value in request.data.items() if key in allowed_fields}

		serializer = RiderAppProfileSerializer(rider, data=payload, partial=True)
		if not serializer.is_valid():
			return api_response(
				error_message=serializer.errors,
				is_success=False,
				status_code=status.HTTP_400_BAD_REQUEST,
			)

		serializer.save()
		return api_response(result=serializer.data, is_success=True, status_code=status.HTTP_200_OK)


class RiderAppAvailabilityUpdateAPIView(APIView):
	"""
	Update authenticated rider availability status.
	"""

	permission_classes = [permissions.IsAuthenticated, IsRiderUser]

	def post(self, request):
		return self._update(request)

	def patch(self, request):
		return self._update(request)

	def _update(self, request):
		rider = _get_authenticated_rider(request.user)
		serializer = RiderAppAvailabilityUpdateSerializer(data=request.data)
		if not serializer.is_valid():
			return api_response(
				error_message=serializer.errors,
				is_success=False,
				status_code=status.HTTP_400_BAD_REQUEST,
			)

		if rider.operational_status != Rider.OperationalStatus.ACTIVE:
			return api_response(
				error_message='Cannot update availability. Your account is not active.',
				result={'operational_status': rider.operational_status},
				is_success=False,
				status_code=status.HTTP_403_FORBIDDEN,
			)

		rider.availability_status = serializer.validated_data['status']
		rider.save(update_fields=['availability_status', 'updated_at'])

		return api_response(
			result={
				'message': 'Availability status updated successfully',
				'status': rider.availability_status,
			},
			is_success=True,
			status_code=status.HTTP_200_OK,
		)


class RiderAssignedOrderListAPIView(generics.ListAPIView):
	"""
	List active orders assigned to the authenticated rider.
	"""

	serializer_class = RiderAssignedOrderListSerializer
	permission_classes = [permissions.IsAuthenticated, IsRiderUser]

	def get_queryset(self):
		rider = _get_authenticated_rider(self.request.user)
		queryset = RiderOrderAssignment.objects.select_related(
			'order',
		).filter(
			rider=rider,
			is_active=True,
		)

		order_status = self.request.query_params.get('status')
		if order_status:
			queryset = queryset.filter(order__status=order_status)

		return queryset

	def list(self, request, *args, **kwargs):
		serializer = self.get_serializer(self.get_queryset(), many=True)
		return api_response(result=serializer.data, is_success=True, status_code=status.HTTP_200_OK)


class RiderOrderHistoryListAPIView(generics.ListAPIView):
	"""
	List historical (completed / returned) orders for the authenticated rider.
	Returns assignments where is_active=False, ordered by most recently unassigned.
	"""

	serializer_class = RiderAssignedOrderListSerializer
	permission_classes = [permissions.IsAuthenticated, IsRiderUser]

	def get_queryset(self):
		rider = _get_authenticated_rider(self.request.user)
		return RiderOrderAssignment.objects.select_related(
			'order',
		).filter(
			rider=rider,
			is_active=False,
		).order_by('-unassigned_at')

	def list(self, request, *args, **kwargs):
		serializer = self.get_serializer(self.get_queryset(), many=True)
		return api_response(result=serializer.data, is_success=True, status_code=status.HTTP_200_OK)


class RiderAssignedOrderDetailAPIView(generics.RetrieveAPIView):
	"""
	Get details of a single assigned order for authenticated rider.
	"""

	serializer_class = RiderAssignedOrderDetailSerializer
	permission_classes = [permissions.IsAuthenticated, IsRiderUser]
	lookup_field = 'order__order_number'
	lookup_url_kwarg = 'order_number'

	def get_queryset(self):
		rider = _get_authenticated_rider(self.request.user)
		# No is_active filter — riders must be able to view completed/returned
		# orders immediately after a terminal status update sets is_active=False.
		return RiderOrderAssignment.objects.select_related(
			'order',
		).prefetch_related(
			'location_updates',
		).filter(
			rider=rider,
		)

	def retrieve(self, request, *args, **kwargs):
		instance = self.get_object()
		serializer = self.get_serializer(instance)
		tracking_history = OrderTracking.objects.filter(order=instance.order).order_by('-created_at')
		tracking_data = [
			{
				'status': item.status,
				'location_city': item.location_city,
				'remarks': item.remarks,
				'created_at': item.created_at.strftime('%Y-%m-%d %H:%M:%S'),
			}
			for item in tracking_history
		]
		response_data = serializer.data
		response_data['tracking_history'] = tracking_data
		return api_response(result=response_data, is_success=True, status_code=status.HTTP_200_OK)


class RiderAssignedOrderStatusUpdateAPIView(APIView):
	"""
	Update status of an order assigned to authenticated rider.
	"""

	permission_classes = [permissions.IsAuthenticated, IsRiderUser]

	# Rider-permitted status transitions.
	ALLOWED_TRANSITIONS = {
		Order.OrderStatus.PICKUP_ASSIGNED:   {Order.OrderStatus.HEADING_TO_PICKUP},
		Order.OrderStatus.HEADING_TO_PICKUP: {Order.OrderStatus.PICKED_UP},
		Order.OrderStatus.OUT_FOR_DELIVERY:  {
			Order.OrderStatus.DELIVERED,
			Order.OrderStatus.RETURNED,
		},
	}

	def patch(self, request, order_number):
		rider = _get_authenticated_rider(request.user)
		serializer = RiderOrderStatusUpdateSerializer(data=request.data)
		if not serializer.is_valid():
			return api_response(error_message=serializer.errors, is_success=False, status_code=status.HTTP_400_BAD_REQUEST)

		assignment = get_object_or_404(
			RiderOrderAssignment.objects.select_related('order'),
			rider=rider,
			is_active=True,
			order__order_number=order_number,
		)
		order = assignment.order
		new_status = serializer.validated_data['status']
		current_status = order.status

		allowed_next_statuses = self.ALLOWED_TRANSITIONS.get(current_status, set())
		if new_status not in allowed_next_statuses:
			return api_response(
				error_message=f'Invalid status transition from {current_status} to {new_status}.',
				is_success=False,
				status_code=status.HTTP_400_BAD_REQUEST,
			)

		now = timezone.now()
		order.status = new_status
		update_fields = ['status', 'updated_at']
		if new_status == Order.OrderStatus.PICKED_UP:
			order.picked_up_at = now
			update_fields.append('picked_up_at')
		if new_status == Order.OrderStatus.DELIVERED:
			order.delivered_at = now
			update_fields.append('delivered_at')
		order.save(update_fields=update_fields)

		location_city = serializer.validated_data.get('location_city') or (
			order.receiver_city if new_status == Order.OrderStatus.DELIVERED else order.sender_city
		)
		remarks = serializer.validated_data.get('remarks', '').strip()
		if not remarks:
			if new_status == Order.OrderStatus.HEADING_TO_PICKUP:
				remarks = 'Rider is on the way to pick up your parcel.'
			elif new_status == Order.OrderStatus.PICKED_UP:
				remarks = 'Rider picked up the parcel from sender.'
			elif new_status == Order.OrderStatus.OUT_FOR_DELIVERY:
				remarks = 'Rider took the parcel out for delivery.'
			elif new_status == Order.OrderStatus.DELIVERED:
				remarks = 'Rider successfully delivered the parcel.'
			elif new_status == Order.OrderStatus.RETURNED:
				remarks = 'Rider returned the parcel (delivery failed).'
			else:
				remarks = f'Rider updated order status to {new_status}.'

		OrderTracking.objects.create(
			order=order,
			status=new_status,
			location_city=location_city,
			remarks=remarks,
		)

		# ── Notifications ───────────────────────────────────────────────────────
		# Fire a push notification to the consumer for the heading_to_pickup event.
		# Only applies to online orders that have a registered consumer.
		if (
			new_status == Order.OrderStatus.HEADING_TO_PICKUP
			and order.order_type == Order.OrderType.ONLINE
			and order.consumer_id
		):
			try:
				PushNotificationService.send_heading_to_pickup_notification(
					user_id=order.consumer_id,
					order_number=order.order_number,
				)
			except Exception:
				# Never let a notification failure break the status update
				pass

		# ── Assignment deactivation on terminal statuses ─────────────────────────
		if new_status in [
			Order.OrderStatus.DELIVERED,
			Order.OrderStatus.RETURNED,
		]:
			assignment.is_active = False
			assignment.unassigned_at = now
			assignment.save(update_fields=['is_active', 'unassigned_at'])

			if not RiderOrderAssignment.objects.filter(rider=rider, is_active=True).exists():
				if rider.availability_status != Rider.AvailabilityStatus.AVAILABLE:
					rider.availability_status = Rider.AvailabilityStatus.AVAILABLE
					rider.save(update_fields=['availability_status', 'updated_at'])

		response_data = RiderAssignedOrderDetailSerializer(assignment).data
		return api_response(result=response_data, is_success=True, status_code=status.HTTP_200_OK)


class RiderOrderLiveLocationUpdateAPIView(APIView):
	"""
	Accept live location updates for the rider's assigned order.
	"""

	permission_classes = [permissions.IsAuthenticated, IsRiderUser]

	def post(self, request, order_number):
		rider = _get_authenticated_rider(request.user)
		serializer = RiderLiveLocationUpdateSerializer(data=request.data)
		if not serializer.is_valid():
			return api_response(error_message=serializer.errors, is_success=False, status_code=status.HTTP_400_BAD_REQUEST)

		assignment = get_object_or_404(
			RiderOrderAssignment.objects.select_related('order'),
			rider=rider,
			is_active=True,
			order__order_number=order_number,
		)

		rider.update_location(
			serializer.validated_data['latitude'],
			serializer.validated_data['longitude'],
		)

		location_update = RiderLocationUpdate.objects.create(
			assignment=assignment,
			order=assignment.order,
			rider=rider,
			latitude=serializer.validated_data['latitude'],
			longitude=serializer.validated_data['longitude'],
			accuracy_meters=serializer.validated_data.get('accuracy_meters'),
			speed_kmh=serializer.validated_data.get('speed_kmh'),
			heading_degrees=serializer.validated_data.get('heading_degrees'),
		)

		response_data = RiderLocationUpdateResponseSerializer(location_update).data
		return api_response(result=response_data, is_success=True, status_code=status.HTTP_201_CREATED)
