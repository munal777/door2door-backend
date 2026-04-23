from rest_framework import serializers
from django.db import transaction

from ..models import TransportBucket, BucketStop, BucketOrder, BucketTracking, Order
from pricings.models import LocationPricing
from myproject.utils import format_datetime


class BucketStopSerializer(serializers.ModelSerializer):
    """Serializer for bucket stop information"""
    orders_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BucketStop
        fields = ['id', 'city', 'state', 'stop_order', 'orders_count']
        read_only_fields = ['id']
    
    def get_orders_count(self, obj):
        return obj.orders_for_this_stop.count()
    
    def validate_city(self, value):
        """Validate that city exists in LocationPricing (serviceable locations)"""
        if not LocationPricing.objects.filter(city__iexact=value, is_active=True).exists():
            raise serializers.ValidationError(
                f"City '{value}' is not in our serviceable locations. Please add it to Location Pricing first."
            )
        return value
    
    def validate_state(self, value):
        """Validate that state is provided"""
        if not value or not value.strip():
            raise serializers.ValidationError("State is required for each stop.")
        return value


class BucketOrderSerializer(serializers.ModelSerializer):
    """Serializer for orders in a bucket"""
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    receiver_city = serializers.CharField(source='order.receiver_city', read_only=True)
    receiver_name = serializers.CharField(source='order.receiver_name', read_only=True)
    package_type = serializers.CharField(source='order.get_package_type_display', read_only=True)
    weight = serializers.DecimalField(source='order.weight', max_digits=10, decimal_places=2, read_only=True)
    added_at = serializers.SerializerMethodField()
    
    class Meta:
        model = BucketOrder
        fields = [
            'id',
            'order_number',
            'receiver_city',
            'receiver_name',
            'package_type',
            'weight',
            'added_at'
        ]
        read_only_fields = ['id', 'added_at']
    
    def get_added_at(self, obj):
        return format_datetime(obj.added_at)


class TransportBucketCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a transport bucket"""
    stops = BucketStopSerializer(many=True, required=True)
    
    class Meta:
        model = TransportBucket
        fields = ['origin_city', 'origin_state', 'stops']
    
    def validate_origin_city(self, value):
        """Validate that origin city exists in LocationPricing (serviceable locations)"""
        if not LocationPricing.objects.filter(city__iexact=value, is_active=True).exists():
            raise serializers.ValidationError(
                f"Origin city '{value}' is not in our serviceable locations. Please add it to Location Pricing first."
            )
        return value
    
    def validate_origin_state(self, value):
        """Validate that origin state is provided"""
        if not value or not value.strip():
            raise serializers.ValidationError("Origin state is required.")
        return value
    
    def validate(self, data):
        """Cross-field validation for bucket creation"""
        origin_city = data.get('origin_city')
        stops = data.get('stops', [])
        
        if not stops:
            raise serializers.ValidationError({
                'stops': 'At least one stop is required for the bucket route.'
            })
        
        
        # Check origin city is not in stops
        stop_cities = [stop['city'].lower() for stop in stops]
        if origin_city.lower() in stop_cities:
            raise serializers.ValidationError({
                'stops': f"Departing location '{origin_city}' should not be included in stops."
            })
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        stops_data = validated_data.pop('stops', [])
        request = self.context.get('request')
        
        # Create bucket
        bucket = TransportBucket.objects.create(
            **validated_data,
            courier_provider=request.courier,
            created_by=request.user
        )
        
        # Create stops if provided
        for stop_data in stops_data:
            BucketStop.objects.create(bucket=bucket, **stop_data)
        
        return bucket


class TransportBucketDetailSerializer(serializers.ModelSerializer):
    """Detailed bucket information"""
    stops = BucketStopSerializer(many=True, read_only=True)
    orders = BucketOrderSerializer(source='bucket_orders', many=True, read_only=True)
    order_count = serializers.IntegerField(read_only=True)
    created_by_name = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    closed_at = serializers.SerializerMethodField()
    
    class Meta:
        model = TransportBucket
        fields = [
            'id',
            'bucket_number',
            'origin_city',
            'origin_state',
            'stops',
            'orders',
            'order_count',
            'created_by_name',
            'created_at',
            'closed_at'
        ]
        read_only_fields = ['id', 'bucket_number', 'order_count']
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.full_name
        return None
    
    def get_created_at(self, obj):
        return format_datetime(obj.created_at)
    
    def get_closed_at(self, obj):
        return format_datetime(obj.closed_at)


class AddOrderToBucketSerializer(serializers.Serializer):
    """Serializer for adding orders to a bucket"""
    order_numbers = serializers.ListField(
        child=serializers.CharField(max_length=50),
        min_length=1,
        help_text="List of order numbers to add to bucket"
    )
    
    def validate_order_numbers(self, value):
        """Validate that all orders exist and can be added"""
        request = self.context.get('request')
        courier_provider = request.courier
        
        # Check all orders exist and belong to this courier
        orders = Order.objects.filter(
            order_number__in=value,
            courier_provider=courier_provider
        )
        
        if orders.count() != len(value):
            found_numbers = set(orders.values_list('order_number', flat=True))
            missing = set(value) - found_numbers
            raise serializers.ValidationError(
                f"Orders not found or don't belong to your company: {', '.join(missing)}"
            )
        
        # Check orders are in valid status (not delivered, cancelled, etc.)
        invalid_orders = orders.exclude(
            status__in=[
                Order.OrderStatus.CONFIRMED,
                Order.OrderStatus.PICKED_UP,
                Order.OrderStatus.AT_ORIGIN_HUB
            ]
        )
        
        if invalid_orders.exists():
            invalid_numbers = invalid_orders.values_list('order_number', flat=True)
            raise serializers.ValidationError(
                f"Orders are not in valid status for bucket: {', '.join(invalid_numbers)}"
            )
        
        return value


class BucketTrackingSerializer(serializers.ModelSerializer):
    """Serializer for bucket tracking events"""
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    scanned_by_name = serializers.SerializerMethodField()
    bucket_number = serializers.CharField(source='bucket.bucket_number', read_only=True)
    stop_city = serializers.CharField(source='bucket_stop.city', read_only=True, allow_null=True)
    created_at = serializers.SerializerMethodField()
    
    class Meta:
        model = BucketTracking
        fields = [
            'id',
            'bucket_number',
            'action',
            'action_display',
            'location_city',
            'stop_city',
            'orders_updated_count',
            'notes',
            'scanned_by_name',
            'created_at'
        ]
        read_only_fields = ['id', 'orders_updated_count']
    
    def get_scanned_by_name(self, obj):
        if obj.scanned_by:
            return obj.scanned_by.full_name
        return None
    
    def get_created_at(self, obj):
        return format_datetime(obj.created_at)


class BucketLocationUpdateSerializer(serializers.Serializer):
    """Serializer for updating bucket location and tracking status"""
    action = serializers.ChoiceField(choices=BucketTracking.ScanAction.choices)
    location_city = serializers.CharField(max_length=100)
    bucket_stop_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate(self, data):
        """Validate bucket location update data"""
        action = data.get('action')
        bucket_stop_id = data.get('bucket_stop_id')
        
        # PARTIAL_UNLOAD requires a bucket_stop
        if action == BucketTracking.ScanAction.PARTIAL_UNLOAD and not bucket_stop_id:
            raise serializers.ValidationError({
                'bucket_stop_id': 'Required for partial unload action'
            })
        
        # Validate bucket_stop belongs to this bucket
        if bucket_stop_id:
            bucket = self.context.get('bucket')
            if not bucket.stops.filter(id=bucket_stop_id).exists():
                raise serializers.ValidationError({
                    'bucket_stop_id': 'Stop does not belong to this bucket'
                })
        
        return data
