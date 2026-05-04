from django.shortcuts import get_object_or_404
from django.db.models import Prefetch

from rest_framework import generics, permissions, status
from rest_framework.views import APIView

from accounts.models import Rider
from myproject.permissions import HasRiderManagementPermission, IsCourierStaff
from myproject.utils import api_response
from orders.models import Order
from riders.models import RiderOrderAssignment
from riders.services import RiderAssignmentService, RiderAssignmentError

from riders.serializers.courier_crm import (
    AssignableOnlineOrderSerializer,
    AssignOnlineOrderToRiderSerializer,
    CourierRiderStatusUpdateSerializer,
    RiderManagementDetailSerializer,
    RiderManagementListSerializer,
    RiderOrderAssignmentSerializer,
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
