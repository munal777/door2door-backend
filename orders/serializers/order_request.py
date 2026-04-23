from rest_framework import serializers
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from ..models import OrderRequest
from myproject.utils import format_datetime


class OrderRequestCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for consumer to submit an online order request.
    The backend calculates the estimated price from the submitted shipment details.
    """

    class Meta:
        model = OrderRequest
        fields = [
            # Pickup
            'pickup_name',
            'pickup_phone',
            'pickup_address',
            'pickup_city',
            'pickup_state',
            'pickup_latitude',
            'pickup_longitude',
            # Delivery
            'delivery_name',
            'delivery_phone',
            'delivery_address',
            'delivery_city',
            'delivery_state',
            'delivery_latitude',
            'delivery_longitude',
            # Package
            'package_type',
            'weight',
            'total_quantity',
            'length',
            'width',
            'height',
            'package_description',
            # Service & Pricing
            'service_type',
            'payment_method',
            'estimated_price',
        ]

        extra_kwargs = {
            # Backward-compatible with existing clients.
            'total_quantity': {'required': False},
            'payment_method': {'required': False},
        }

    def validate_weight(self, value):
        if value <= 0:
            raise serializers.ValidationError("Weight must be greater than 0.")
        return value

    def validate_estimated_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Estimated price must be greater than 0.")
        return value

    def validate(self, data):
        service_type = data.get('service_type')
        weight = data.get('weight')
        quantity = data.get('total_quantity') or 1
        total_weight = weight * quantity

        if service_type == OrderRequest.ServiceType.EXPRESS and total_weight > 25:
            raise serializers.ValidationError({'weight': 'Express delivery cannot exceed 25 kg.'})
        if service_type == OrderRequest.ServiceType.STANDARD and total_weight > 50:
            raise serializers.ValidationError({'weight': 'Standard delivery cannot exceed 50 kg.'})
        return data

    @transaction.atomic
    def create(self, validated_data):
        request = self.context['request']
        return OrderRequest.objects.create(
            **validated_data,
            consumer=request.user,
            expires_at=timezone.now() + timedelta(hours=24),
        )


class OrderRequestHistorySerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the consumer's request history list.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    package_type_display = serializers.CharField(source='get_package_type_display', read_only=True)
    service_type_display = serializers.CharField(source='get_service_type_display', read_only=True)
    order_number = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    payment_status_display = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    payment_method_display = serializers.SerializerMethodField()
    can_pay_with_esewa = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    expires_at = serializers.SerializerMethodField()
    responded_at = serializers.SerializerMethodField()

    class Meta:
        model = OrderRequest
        fields = [
            'id',
            'request_number',
            'status_display',
            'pickup_city',
            'delivery_city',
            'package_type_display',
            'service_type_display',
            'total_quantity',
            'estimated_price',
            'order_number',
            'payment_status',
            'payment_status_display',
            'payment_method',
            'payment_method_display',
            'can_pay_with_esewa',
            'created_at',
            'expires_at',
            'responded_at',
        ]
        read_only_fields = fields

    def get_order_number(self, obj):
        if hasattr(obj, 'order') and obj.order:
            return obj.order.order_number
        return None

    def get_payment_status(self, obj):
        if hasattr(obj, 'order') and obj.order:
            return obj.order.payment_status
        return None

    def get_payment_status_display(self, obj):
        if hasattr(obj, 'order') and obj.order:
            return obj.order.get_payment_status_display()
        return None

    def get_payment_method(self, obj):
        if hasattr(obj, 'order') and obj.order:
            return obj.order.payment_method
        return obj.payment_method

    def get_payment_method_display(self, obj):
        if hasattr(obj, 'order') and obj.order:
            return obj.order.get_payment_method_display()
        return obj.get_payment_method_display()

    def get_can_pay_with_esewa(self, obj):
        if not hasattr(obj, 'order') or not obj.order:
            return False
        return (
            obj.order.payment_method == obj.order.PaymentMethod.ESEWA
            and obj.order.payment_status != obj.order.PaymentStatus.PAID
        )

    def get_created_at(self, obj):
        return format_datetime(obj.created_at)

    def get_expires_at(self, obj):
        return format_datetime(obj.expires_at)

    def get_responded_at(self, obj):
        return format_datetime(obj.responded_at)


class OrderRequestDetailSerializer(serializers.ModelSerializer):
    """
    Read serializer for a consumer's order request, including resolved order number
    when the request has been accepted.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    package_type_display = serializers.CharField(source='get_package_type_display', read_only=True)
    service_type_display = serializers.CharField(source='get_service_type_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    accepted_by_courier_name = serializers.SerializerMethodField()
    order_number = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    expires_at = serializers.SerializerMethodField()
    responded_at = serializers.SerializerMethodField()

    class Meta:
        model = OrderRequest
        fields = [
            'id',
            'request_number',
            'status_display',
            # Pickup
            'pickup_name',
            'pickup_phone',
            'pickup_address',
            'pickup_city',
            'pickup_state',
            'pickup_latitude',
            'pickup_longitude',
            # Delivery
            'delivery_name',
            'delivery_phone',
            'delivery_address',
            'delivery_city',
            'delivery_state',
            'delivery_latitude',
            'delivery_longitude',
            # Package
            'package_type_display',
            'weight',
            'total_quantity',
            'length',
            'width',
            'height',
            'package_description',
            # Service & Pricing
            'service_type_display',
            'payment_method_display',
            'estimated_price',
            # Response info
            'accepted_by_courier_name',
            'rejection_reason',
            'order_number',
            # Timestamps
            'created_at',
            'expires_at',
            'responded_at',
        ]
        read_only_fields = fields

    def get_accepted_by_courier_name(self, obj):
        return obj.accepted_by.name if obj.accepted_by else None

    def get_order_number(self, obj):
        """Return the resulting order number once the request has been accepted."""
        if hasattr(obj, 'order') and obj.order:
            return obj.order.order_number
        return None

    def get_created_at(self, obj):
        return format_datetime(obj.created_at)

    def get_expires_at(self, obj):
        return format_datetime(obj.expires_at)

    def get_responded_at(self, obj):
        return format_datetime(obj.responded_at)


class NearbyOrderRequestListSerializer(serializers.ModelSerializer):
    """
    Lightweight read serializer for courier nearby request feed.
    Requests are visible when pickup city/state matches courier city/state.
    """
    package_type_display = serializers.CharField(source='get_package_type_display', read_only=True)
    service_type_display = serializers.CharField(source='get_service_type_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    created_at = serializers.SerializerMethodField()
    expires_at = serializers.SerializerMethodField()

    class Meta:
        model = OrderRequest
        fields = [
            'id',
            'request_number',
            'pickup_city',
            'pickup_state',
            'delivery_city',
            'delivery_state',
            'package_type_display',
            'weight',
            'total_quantity',
            'service_type_display',
            'payment_method_display',
            'estimated_price',
            'created_at',
            'expires_at',
        ]
        read_only_fields = fields

    def get_created_at(self, obj):
        return format_datetime(obj.created_at)

    def get_expires_at(self, obj):
        return format_datetime(obj.expires_at)


class NearbyOrderRequestDetailSerializer(serializers.ModelSerializer):
    """
    Detail read serializer for courier nearby request view.
    """
    package_type_display = serializers.CharField(source='get_package_type_display', read_only=True)
    service_type_display = serializers.CharField(source='get_service_type_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    created_at = serializers.SerializerMethodField()
    expires_at = serializers.SerializerMethodField()

    class Meta:
        model = OrderRequest
        fields = [
            'id',
            'request_number',
            # Pickup
            'pickup_name',
            'pickup_phone',
            'pickup_address',
            'pickup_city',
            'pickup_state',
            'pickup_latitude',
            'pickup_longitude',
            # Delivery
            'delivery_name',
            'delivery_phone',
            'delivery_address',
            'delivery_city',
            'delivery_state',
            'delivery_latitude',
            'delivery_longitude',
            # Package
            'package_type_display',
            'weight',
            'total_quantity',
            'length',
            'width',
            'height',
            'package_description',
            # Service/Pricing
            'service_type_display',
            'payment_method_display',
            'estimated_price',
            # Timestamps
            'created_at',
            'expires_at',
        ]
        read_only_fields = fields

    def get_created_at(self, obj):
        return format_datetime(obj.created_at)

    def get_expires_at(self, obj):
        return format_datetime(obj.expires_at)


class NearbyOrderRequestActionSerializer(serializers.Serializer):
    """
    Serializer for courier action on nearby order request.
    """
    ACTION_ACCEPT = 'accept'
    ACTION_DECLINE = 'decline'
    ACTION_IGNORE = 'ignore'

    action = serializers.ChoiceField(
        choices=[
            (ACTION_ACCEPT, 'Accept'),
            (ACTION_DECLINE, 'Decline'),
            (ACTION_IGNORE, 'Ignore'),
        ]
    )
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
