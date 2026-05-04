from rest_framework import serializers

from accounts.models import Rider
from orders.models import Order
from riders.models import RiderOrderAssignment
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
