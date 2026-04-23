from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from django.utils import timezone

from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied

from accounts.models import Rider
from myproject.permissions import (
	HasRiderManagementPermission,
	IsCourierStaff,
	IsRiderUser,
)
from myproject.utils import api_response
from orders.models import Order, OrderTracking
from riders.serializers import (
    AssignableOnlineOrderSerializer,
	AssignOnlineOrderToRiderSerializer,
	CourierRiderStatusUpdateSerializer,
	RiderAppAvailabilityUpdateSerializer,
	RiderAppProfileSerializer,
	RiderManagementDetailSerializer,
	RiderManagementListSerializer,
	RiderAssignedOrderDetailSerializer,
	RiderAssignedOrderListSerializer,
	RiderLiveLocationUpdateSerializer,
	RiderLocationUpdateResponseSerializer,
	RiderOrderStatusUpdateSerializer,
	RiderOrderAssignmentSerializer,
)
from riders.models import RiderLocationUpdate, RiderOrderAssignment
from riders.services import RiderAssignmentService, RiderAssignmentError


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


class CourierRiderListAPIView(generics.ListAPIView):
	"""
	List riders for authenticated courier provider.
	"""

	serializer_class = RiderManagementListSerializer
	permission_classes = [permissions.IsAuthenticated, IsCourierStaff]

	def get_queryset(self):
		courier_provider = self.request.courier
		queryset = Rider.objects.select_related('user', 'company').filter(company=courier_provider)

		availability = self.request.query_params.get('availability_status')
		if availability:
			queryset = queryset.filter(availability_status=availability)

		operational = self.request.query_params.get('operational_status')
		if operational:
			queryset = queryset.filter(operational_status=operational)

		return queryset

	def list(self, request, *args, **kwargs):
		serializer = self.get_serializer(self.get_queryset(), many=True)
		return api_response(result=serializer.data, is_success=True, status_code=status.HTTP_200_OK)


class CourierRiderDetailAPIView(generics.RetrieveAPIView):
	"""
	Get rider details for authenticated courier provider.
	"""

	serializer_class = RiderManagementDetailSerializer
	permission_classes = [permissions.IsAuthenticated, IsCourierStaff]

	def get_queryset(self):
		return Rider.objects.select_related('user', 'company').filter(company=self.request.courier)

	def retrieve(self, request, *args, **kwargs):
		instance = self.get_object()
		serializer = self.get_serializer(instance)
		return api_response(result=serializer.data, is_success=True, status_code=status.HTTP_200_OK)


class CourierRiderStatusUpdateAPIView(APIView):
	"""
	Update rider operational/availability status for authenticated courier provider.
	"""

	permission_classes = [permissions.IsAuthenticated, HasRiderManagementPermission]

	def patch(self, request, pk):
		rider = get_object_or_404(Rider, pk=pk, company=request.courier)
		serializer = CourierRiderStatusUpdateSerializer(data=request.data)

		if not serializer.is_valid():
			return api_response(
				error_message=serializer.errors,
				is_success=False,
				status_code=status.HTTP_400_BAD_REQUEST,
			)

		updated_fields = []
		operational_status = serializer.validated_data.get('operational_status')
		availability_status = serializer.validated_data.get('availability_status')

		if operational_status is not None:
			rider.operational_status = operational_status
			updated_fields.append('operational_status')

		# Enforce offline availability when rider is not active.
		if rider.operational_status != Rider.OperationalStatus.ACTIVE:
			if rider.availability_status != Rider.AvailabilityStatus.OFFLINE:
				rider.availability_status = Rider.AvailabilityStatus.OFFLINE
				updated_fields.append('availability_status')
		elif availability_status is not None:
			rider.availability_status = availability_status
			updated_fields.append('availability_status')

		if updated_fields:
			rider.save(update_fields=list(set(updated_fields + ['updated_at'])))

		response_serializer = RiderManagementDetailSerializer(rider)
		return api_response(result=response_serializer.data, is_success=True, status_code=status.HTTP_200_OK)


class AssignOnlineOrderToRiderAPIView(APIView):
	"""
	Assign (or reassign) a confirmed online order to a rider for pickup.
	"""

	permission_classes = [permissions.IsAuthenticated, HasRiderManagementPermission]

	def post(self, request, order_number):
		serializer = AssignOnlineOrderToRiderSerializer(data=request.data)
		if not serializer.is_valid():
			return api_response(
				error_message=serializer.errors,
				is_success=False,
				status_code=status.HTTP_400_BAD_REQUEST,
			)

		courier_provider = request.courier

		order = get_object_or_404(Order, order_number=order_number, courier_provider=courier_provider)
		rider = get_object_or_404(Rider, id=serializer.validated_data['rider_id'], company=courier_provider)

		try:
			assignment = RiderAssignmentService.assign_online_order_for_pickup(
				order=order,
				rider=rider,
				assigned_by=request.user,
				notes=serializer.validated_data.get('notes', ''),
			)
		except RiderAssignmentError as exc:
			return api_response(
				error_message=str(exc),
				is_success=False,
				status_code=status.HTTP_400_BAD_REQUEST,
			)

		response_serializer = RiderOrderAssignmentSerializer(assignment)
		return api_response(
			result=response_serializer.data,
			is_success=True,
			status_code=status.HTTP_200_OK,
		)


class ActiveRiderAssignmentListAPIView(generics.ListAPIView):
	"""
	List active rider assignments for authenticated courier provider.
	"""

	serializer_class = RiderOrderAssignmentSerializer
	permission_classes = [permissions.IsAuthenticated, IsCourierStaff]

	def get_queryset(self):
		courier_provider = self.request.courier
		queryset = RiderOrderAssignment.objects.select_related(
			'order',
			'rider__user',
			'assigned_by',
		).filter(
			is_active=True,
			order__courier_provider=courier_provider,
		)

		rider_id = self.request.query_params.get('rider_id')
		if rider_id:
			queryset = queryset.filter(rider_id=rider_id)

		order_status = self.request.query_params.get('order_status')
		if order_status:
			queryset = queryset.filter(order__status=order_status)

		return queryset

	def list(self, request, *args, **kwargs):
		serializer = self.get_serializer(self.get_queryset(), many=True)
		return api_response(result=serializer.data, is_success=True, status_code=status.HTTP_200_OK)


class AssignableOnlineOrderListAPIView(generics.ListAPIView):
	"""
	List online orders that can be assigned to riders, with shipment details.
	"""

	serializer_class = AssignableOnlineOrderSerializer
	permission_classes = [permissions.IsAuthenticated, IsCourierStaff]

	def get_queryset(self):
		courier_provider = self.request.courier
		active_assignment_queryset = RiderOrderAssignment.objects.select_related('rider__user').filter(
			is_active=True,
		)

		queryset = Order.objects.filter(
			courier_provider=courier_provider,
			order_type=Order.OrderType.ONLINE,
			status__in=[Order.OrderStatus.CONFIRMED, Order.OrderStatus.PICKUP_ASSIGNED],
		).prefetch_related(
			Prefetch('rider_assignments', queryset=active_assignment_queryset, to_attr='active_rider_assignments'),
		).order_by('-created_at')

		search = self.request.query_params.get('search')
		if search:
			queryset = queryset.filter(
				order_number__icontains=search,
			)

		return queryset

	def list(self, request, *args, **kwargs):
		serializer = self.get_serializer(self.get_queryset(), many=True)
		return api_response(result=serializer.data, is_success=True, status_code=status.HTTP_200_OK)


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
		return RiderOrderAssignment.objects.select_related(
			'order',
		).prefetch_related(
			'location_updates',
		).filter(
			rider=rider,
			is_active=True,
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

	ALLOWED_TRANSITIONS = {
		Order.OrderStatus.PICKUP_ASSIGNED: {Order.OrderStatus.PICKED_UP},
		Order.OrderStatus.PICKED_UP: {Order.OrderStatus.IN_TRANSIT},
		Order.OrderStatus.IN_TRANSIT: {Order.OrderStatus.OUT_FOR_DELIVERY},
		Order.OrderStatus.OUT_FOR_DELIVERY: {Order.OrderStatus.DELIVERED},
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
			remarks = f'Rider updated order status to {new_status}.'

		OrderTracking.objects.create(
			order=order,
			status=new_status,
			location_city=location_city,
			remarks=remarks,
		)

		if new_status == Order.OrderStatus.DELIVERED:
			assignment.is_active = False
			assignment.unassigned_at = now
			assignment.save(update_fields=['is_active', 'unassigned_at'])
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
