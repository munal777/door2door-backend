from rest_framework import serializers

from accounts.models import Rider
from orders.models import Order
from .models import RiderOrderAssignment, RiderLocationUpdate
from myproject.utils import format_datetime


class RiderManagementListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Rider
        fields = [
            'id',
            'full_name',
            'email',
            'phone_number',
            'vehicle_type',
            'vehicle_number',
            'operational_status',
            'availability_status',
        ]


class RiderManagementDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    assigned_orders = serializers.SerializerMethodField()

    class Meta:
        model = Rider
        fields = [
            'id',
            'full_name',
            'email',
            'phone_number',
            'company_name',
            'vehicle_type',
            'vehicle_number',
            'vehicle_model',
            'vehicle_color',
            'operational_status',
            'availability_status',
            'current_latitude',
            'current_longitude',
            'last_location_update',
            'assigned_orders',
        ]

    def get_assigned_orders(self, obj):
        assignments = obj.order_assignments.select_related('order').filter(is_active=True)[:10]
        return [
            {
                'assignment_id': assignment.id,
                'order_number': assignment.order.order_number,
                'order_status': assignment.order.status,
                'assigned_at': format_datetime(assignment.assigned_at),
                'notes': assignment.notes,
            }
            for assignment in assignments
        ]


class AssignOnlineOrderToRiderSerializer(serializers.Serializer):
    rider_id = serializers.IntegerField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class RiderOrderAssignmentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    order_status = serializers.CharField(source='order.status', read_only=True)
    rider_name = serializers.CharField(source='rider.user.full_name', read_only=True)
    rider_phone = serializers.CharField(source='rider.user.phone_number', read_only=True)
    assigned_by_name = serializers.SerializerMethodField()
    assigned_at = serializers.SerializerMethodField()

    class Meta:
        model = RiderOrderAssignment
        fields = [
            'id',
            'order_number',
            'order_status',
            'rider',
            'rider_name',
            'rider_phone',
            'notes',
            'is_active',
            'assigned_by_name',
            'assigned_at',
        ]

    def get_assigned_by_name(self, obj):
        if obj.assigned_by:
            return obj.assigned_by.full_name
        return None

    def get_assigned_at(self, obj):
        return format_datetime(obj.assigned_at)


class AssignableOnlineOrderSerializer(serializers.ModelSerializer):
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    package_type_display = serializers.CharField(source='get_package_type_display', read_only=True)
    service_type_display = serializers.CharField(source='get_service_type_display', read_only=True)
    active_rider_name = serializers.SerializerMethodField()
    active_assignment_id = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'order_type_display',
            'status',
            'status_display',
            'sender_name',
            'sender_phone',
            'sender_city',
            'sender_state',
            'receiver_name',
            'receiver_phone',
            'receiver_city',
            'receiver_state',
            'package_type_display',
            'service_type_display',
            'weight',
            'length',
            'width',
            'height',
            'package_description',
            'total_price',
            'active_assignment_id',
            'active_rider_name',
            'created_at',
        ]

    def get_active_assignment_id(self, obj):
        assignments = getattr(obj, 'active_rider_assignments', None)
        assignment = assignments[0] if assignments else None
        if assignment:
            return assignment.id
        return None

    def get_active_rider_name(self, obj):
        assignments = getattr(obj, 'active_rider_assignments', None)
        assignment = assignments[0] if assignments else None
        if assignment and assignment.rider and assignment.rider.user:
            return assignment.rider.user.full_name
        return None

    def get_created_at(self, obj):
        return format_datetime(obj.created_at)


class RiderAssignedOrderListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the rider orders list view.
    Returns only the data needed to render a compact order card.
    Full sender/receiver details are available via the detail endpoint.
    """
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    order_status = serializers.CharField(source='order.status', read_only=True)
    sender_name = serializers.CharField(source='order.sender_name', read_only=True)
    sender_city = serializers.CharField(source='order.sender_city', read_only=True)
    sender_address = serializers.CharField(source='order.sender_address', read_only=True)
    package_type = serializers.CharField(source='order.package_type', read_only=True)
    assigned_at = serializers.SerializerMethodField()

    class Meta:
        model = RiderOrderAssignment
        fields = [
            'id',
            'order_number',
            'order_status',
            'sender_name',
            'sender_city',
            'sender_address',
            'package_type',
            'notes',
            'assigned_at',
        ]

    def get_assigned_at(self, obj):
        return format_datetime(obj.assigned_at)


class RiderAssignedOrderDetailSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    order_status = serializers.CharField(source='order.status', read_only=True)
    sender_name = serializers.CharField(source='order.sender_name', read_only=True)
    sender_phone = serializers.CharField(source='order.sender_phone', read_only=True)
    sender_address = serializers.CharField(source='order.sender_address', read_only=True)
    sender_city = serializers.CharField(source='order.sender_city', read_only=True)
    sender_state = serializers.CharField(source='order.sender_state', read_only=True)
    sender_latitude = serializers.DecimalField(source='order.sender_latitude', max_digits=9, decimal_places=6, read_only=True)
    sender_longitude = serializers.DecimalField(source='order.sender_longitude', max_digits=9, decimal_places=6, read_only=True)
    receiver_name = serializers.CharField(source='order.receiver_name', read_only=True)
    receiver_phone = serializers.CharField(source='order.receiver_phone', read_only=True)
    receiver_address = serializers.CharField(source='order.receiver_address', read_only=True)
    receiver_city = serializers.CharField(source='order.receiver_city', read_only=True)
    receiver_state = serializers.CharField(source='order.receiver_state', read_only=True)
    receiver_latitude = serializers.DecimalField(source='order.receiver_latitude', max_digits=9, decimal_places=6, read_only=True)
    receiver_longitude = serializers.DecimalField(source='order.receiver_longitude', max_digits=9, decimal_places=6, read_only=True)
    package_type = serializers.CharField(source='order.package_type', read_only=True)
    service_type = serializers.CharField(source='order.service_type', read_only=True)
    package_description = serializers.CharField(source='order.package_description', read_only=True)
    weight = serializers.DecimalField(source='order.weight', max_digits=10, decimal_places=2, read_only=True)
    total_price = serializers.DecimalField(source='order.total_price', max_digits=10, decimal_places=2, read_only=True)
    assigned_at = serializers.SerializerMethodField()
    last_location_update_at = serializers.SerializerMethodField()

    class Meta:
        model = RiderOrderAssignment
        fields = [
            'id',
            'order_number',
            'order_status',
            'sender_name',
            'sender_phone',
            'sender_address',
            'sender_city',
            'sender_state',
            'sender_latitude',
            'sender_longitude',
            'receiver_name',
            'receiver_phone',
            'receiver_address',
            'receiver_city',
            'receiver_state',
            'receiver_latitude',
            'receiver_longitude',
            'package_type',
            'service_type',
            'package_description',
            'weight',
            'total_price',
            'notes',
            'assigned_at',
            'last_location_update_at',
        ]

    def get_assigned_at(self, obj):
        return format_datetime(obj.assigned_at)

    def get_last_location_update_at(self, obj):
        latest_update = obj.location_updates.first()
        if latest_update:
            return format_datetime(latest_update.recorded_at)
        return None


class RiderOrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.OrderStatus.choices)
    remarks = serializers.CharField(required=False, allow_blank=True)
    location_city = serializers.CharField(required=False, allow_blank=True)


class RiderLiveLocationUpdateSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    accuracy_meters = serializers.FloatField(min_value=0, required=False)
    speed_kmh = serializers.FloatField(min_value=0, required=False)
    heading_degrees = serializers.FloatField(min_value=0, max_value=360, required=False)


class RiderLocationUpdateResponseSerializer(serializers.ModelSerializer):
    recorded_at = serializers.SerializerMethodField()

    class Meta:
        model = RiderLocationUpdate
        fields = [
            'id',
            'latitude',
            'longitude',
            'accuracy_meters',
            'speed_kmh',
            'heading_degrees',
            'recorded_at',
        ]

    def get_recorded_at(self, obj):
        return format_datetime(obj.recorded_at)


class CourierRiderStatusUpdateSerializer(serializers.Serializer):
    operational_status = serializers.ChoiceField(
        choices=Rider.OperationalStatus.choices,
        required=False,
    )
    availability_status = serializers.ChoiceField(
        choices=Rider.AvailabilityStatus.choices,
        required=False,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Provide at least one status field to update.')
        return attrs


class RiderAppProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = Rider
        fields = [
            'id',
            'first_name',
            'last_name',
            'full_name',
            'email',
            'phone_number',
            'company_name',
            'date_of_birth',
            'emergency_contact_name',
            'emergency_contact_phone',
            'vehicle_type',
            'vehicle_number',
            'vehicle_model',
            'vehicle_color',
            'operational_status',
            'availability_status',
            'current_latitude',
            'current_longitude',
            'last_location_update',
        ]
        read_only_fields = [
            'id',
            'first_name',
            'last_name',
            'full_name',
            'email',
            'phone_number',
            'company_name',
            'vehicle_type',
            'vehicle_number',
            'operational_status',
            'availability_status',
            'current_latitude',
            'current_longitude',
            'last_location_update',
        ]


class RiderAppAvailabilityUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Rider.AvailabilityStatus.choices)
