from rest_framework import serializers
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from ..models import Order, OrderTracking
from pricings.services import PricingEstimationService, PricingEstimationError
from myproject.utils import format_datetime


class ManualOrderCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating manual orders
    """
    
    class Meta:
        model = Order
        fields = [
            # Sender Details
            'sender_name',
            'sender_phone',
            'sender_email',
            'sender_address',
            'sender_city',
            'sender_state',
            
            # Receiver Details
            'receiver_name',
            'receiver_phone',
            'receiver_email',
            'receiver_address',
            'receiver_city',
            'receiver_state',
            
            # Package Details
            'package_type',
            'weight',
            'total_quantity',
            'length',
            'width',
            'height',
            'package_description',
            
            # Service
            'service_type',
            'payment_method',
            'payment_status',
        ]

        extra_kwargs = {
            'total_quantity': {'required': False},
        }
    
    def validate_weight(self, value):
        """Validate weight based on service type"""
        if value <= 0:
            raise serializers.ValidationError("Weight must be greater than 0")
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        service_type = data.get('service_type')
        weight = data.get('weight')
        quantity = data.get('total_quantity') or 1
        total_weight = weight * quantity
        
        # Validate weight limits based on service type
        if service_type == 'express' and total_weight > 25:
            raise serializers.ValidationError({
                'weight': f'Express delivery cannot exceed 25 kg (total: {total_weight} kg with quantity {quantity})'
            })
        elif service_type == 'standard' and total_weight > 50:
            raise serializers.ValidationError({
                'weight': f'Standard delivery cannot exceed 50 kg (total: {total_weight} kg with quantity {quantity})'
            })
        
        # Validate sender and receiver are different
        if (data.get('sender_city', '').lower() == data.get('receiver_city', '').lower() and
            data.get('sender_phone') == data.get('receiver_phone')):
            raise serializers.ValidationError(
                "Sender and receiver cannot be the same (same city, and phone)"
            )
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create manual order with automatic price calculation"""
        # Get courier provider from request context
        request = self.context.get('request')
        courier_provider = request.courier
        
        # Calculate price using pricing service
        try:
            price_estimation = PricingEstimationService.estimate_price(
                package_type=validated_data['package_type'],
                weight=validated_data['weight'],
                quantity=validated_data.get('total_quantity', 1),
                pickup_city=validated_data['sender_city'],
                pickup_state=validated_data['sender_state'],
                delivery_city=validated_data['receiver_city'],
                delivery_state=validated_data['receiver_state'],
                service_type=validated_data['service_type'],
                length=validated_data.get('length'),
                width=validated_data.get('width'),
                height=validated_data.get('height'),
            )
            
            total_price = Decimal(str(price_estimation['total_price']))
 
        except PricingEstimationError as e:
            raise serializers.ValidationError({
                'pricing_error': str(e)
            })
        
        if validated_data['service_type'] == Order.ServiceType.EXPRESS:
            estimated_delivery_hours = 24
        elif validated_data['service_type'] == Order.ServiceType.STANDARD:
            estimated_delivery_hours = 48
        
        # Create order with calculated price
        order = Order.objects.create(
            **validated_data,
            order_type=Order.OrderType.MANUAL,
            courier_provider=courier_provider,
            total_price=total_price,
            estimated_delivery_hours=estimated_delivery_hours,
            status=Order.OrderStatus.CONFIRMED,
            created_by=request.user if hasattr(request.user, 'courier_staff') else None,
        )
        
        # Create initial tracking entry with customer-friendly message
        OrderTracking.objects.create(
            order=order,
            status=Order.OrderStatus.CONFIRMED,
            location_city=validated_data['sender_city'],
            remarks=f"Your order has been confirmed! We have received your shipment at {validated_data['sender_city']} and it will be processed shortly.",
        )
        
        return order


class OrderListSerializer(serializers.ModelSerializer):
    """Compact serializer for order lists"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    package_type_display = serializers.CharField(source='get_package_type_display', read_only=True)
    service_type_display = serializers.CharField(source='get_service_type_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    created_at = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'status_display',
            'sender_name',
            'sender_city',
            'sender_phone',
            'receiver_name',
            'receiver_city',
            'receiver_phone',
            'package_type_display',
            'service_type_display',
            'payment_status_display',
            'total_price',
            'weight',
            'total_quantity',
            'created_at'
        ]
    
    def get_created_at(self, obj):
        return format_datetime(obj.created_at)



class ManualOrderUpdateSerializer(serializers.Serializer):
    """
    Serializer for staff-initiated manual updates to an existing order.
    Only mutable operational fields are exposed — identification, pricing,
    sender/receiver, and courier fields are intentionally excluded.
    """
    # Status updates
    status = serializers.ChoiceField(
        choices=Order.OrderStatus.choices,
        required=False
    )
    payment_status = serializers.ChoiceField(
        choices=Order.PaymentStatus.choices,
        required=False
    )
    payment_method = serializers.ChoiceField(
        choices=Order.PaymentMethod.choices,
        required=False
    )
    # Optional remarks logged to tracking history on status change
    remarks = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        default=''
    )
    # Parcel details — allowed for walk-in / exception corrections
    weight = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        min_value=0.01
    )
    total_quantity = serializers.IntegerField(
        required=False,
        min_value=1
    )
    length = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=0.01
    )
    width = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=0.01
    )
    height = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=0.01
    )
    package_description = serializers.CharField(
        required=False,
        allow_blank=True
    )

    def validate(self, data):
        if not data:
            raise serializers.ValidationError(
                "At least one field must be provided for update."
            )
        return data

    @transaction.atomic
    def update(self, instance, validated_data):
        """Apply the update and create a tracking entry on status change."""
        remarks = validated_data.pop('remarks', '').strip()
        old_status = instance.status
        new_status = validated_data.get('status')

        # Apply all provided fields
        parcel_fields = ['weight', 'total_quantity', 'length', 'width', 'height', 'package_description']
        status_fields = ['status', 'payment_status']
        update_fields = []

        for field in status_fields + parcel_fields:
            if field in validated_data:
                setattr(instance, field, validated_data[field])
                update_fields.append(field)

        # Sync timestamp if status changed to a terminal/milestone state
        if new_status and new_status != old_status:
            if new_status == Order.OrderStatus.PICKED_UP:
                instance.picked_up_at = timezone.now()
                update_fields.append('picked_up_at')
            elif new_status == Order.OrderStatus.DELIVERED:
                instance.delivered_at = timezone.now()
                update_fields.append('delivered_at')
            elif new_status == Order.OrderStatus.CANCELLED:
                instance.cancelled_at = timezone.now()
                update_fields.append('cancelled_at')

        instance.save(update_fields=update_fields)

        # Create tracking entry whenever status changes
        if new_status and new_status != old_status:
            default_remarks = {
                Order.OrderStatus.CONFIRMED: f"Order status manually updated to Confirmed by staff.",
                Order.OrderStatus.PICKUP_ASSIGNED: "Pickup has been assigned for this order.",
                Order.OrderStatus.PICKED_UP: "Package has been picked up from sender.",
                Order.OrderStatus.AT_ORIGIN_HUB: "Package arrived at origin hub.",
                Order.OrderStatus.IN_TRANSIT: "Package is in transit to the destination hub.",
                Order.OrderStatus.AT_DESTINATION_HUB: "Package arrived at destination hub.",
                Order.OrderStatus.OUT_FOR_DELIVERY: "Package is out for delivery.",
                Order.OrderStatus.DELIVERED: "Package has been successfully delivered.",
                Order.OrderStatus.CANCELLED: "Order has been cancelled.",
                Order.OrderStatus.RETURNED: "Package is being returned to sender.",
            }
            tracking_remarks = remarks or default_remarks.get(
                new_status,
                f"Order status updated to {instance.get_status_display()} by staff."
            )
            OrderTracking.objects.create(
                order=instance,
                status=new_status,
                location_city=instance.sender_city,
                remarks=tracking_remarks,
            )

        return instance


class OrderDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for manual order display
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    package_type_display = serializers.CharField(source='get_package_type_display', read_only=True)
    service_type_display = serializers.CharField(source='get_service_type_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    
    courier_provider_name = serializers.CharField(source='courier_provider.name', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()
    confirmed_at = serializers.SerializerMethodField()
    picked_up_at = serializers.SerializerMethodField()
    delivered_at = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id',
            'order_number',
            'order_type_display',
            'status_display',
            
            # Sender
            'sender_name',
            'sender_phone',
            'sender_email',
            'sender_address',
            'sender_city',
            'sender_state',
            
            # Receiver
            'receiver_name',
            'receiver_phone',
            'receiver_email',
            'receiver_address',
            'receiver_city',
            'receiver_state',
            
            # Package
            'package_type_display',
            'weight',
            'total_quantity',
            'length',
            'width',
            'height',
            'package_description',
            
            # Service
            'service_type_display',
            'estimated_delivery_hours',
            'total_price',
            
            # Payment
            'payment_method_display',
            'payment_status_display',
            
            # Courier
            'courier_provider_name',
            'created_by_name',
            
            # Timestamps
            'created_at',
            'updated_at',
            'confirmed_at',
            'picked_up_at',
            'delivered_at',
        ]
        read_only_fields = ['id', 'order_number', 'created_at', 'updated_at']
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.full_name
        return None
    
    def get_created_at(self, obj):
        return format_datetime(obj.created_at)
    
    def get_updated_at(self, obj):
        return format_datetime(obj.updated_at)
    
    def get_confirmed_at(self, obj):
        return format_datetime(obj.confirmed_at)
    
    def get_picked_up_at(self, obj):
        return format_datetime(obj.picked_up_at)
    
    def get_delivered_at(self, obj):
        return format_datetime(obj.delivered_at)
