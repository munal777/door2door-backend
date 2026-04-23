from rest_framework import serializers
from decimal import Decimal
from .models import WeightSlab, ServiceTypePricing, LocationPricing


class WeightSlabSerializer(serializers.ModelSerializer):
    """
    Serializer for WeightSlab model
    """

    class Meta:
        model = WeightSlab
        fields = [
            'id',
            'package_type',
            'up_to_weight',
            'length',
            'width',
            'height',
            'extra_charge',
            'is_active',
        ]
        read_only_fields = ['id']
    
    def validate_up_to_weight(self, value):
        if value > 50:
            raise serializers.ValidationError("Weight slab cannot exceed 50 kg")
        
        # Only check for duplicates during creation, not updates
        if not self.instance and WeightSlab.objects.filter(up_to_weight=value).exists():
            raise serializers.ValidationError("Weight slab with this value already exists.")
        return value
    
    def validate_length(self, value):
        if value and value > 250:
            raise serializers.ValidationError("Length cannot exceed 250 cm")
        return value
    
    def validate_width(self, value):
        if value and value > 250:
            raise serializers.ValidationError("Width cannot exceed 250 cm")
        return value
    
    def validate_height(self, value):
        if value and value > 250:
            raise serializers.ValidationError("Height cannot exceed 250 cm")
        return value



class ServiceTypePricingSerializer(serializers.ModelSerializer):
    """
    Serializer for ServiceTypePricing model
    """

    class Meta:
        model = ServiceTypePricing
        fields = [
            'id',
            'service_type',
            'estimated_delivery_hours',
            'price_multiplier',
            'is_active',
        ]
        read_only_fields = ['id']
    
    def validate_price_multiplier(self, value):
        if value < Decimal('0.1'):
            raise serializers.ValidationError("Price multiplier cannot be less than 0.1")
        if value > Decimal('10.0'):
            raise serializers.ValidationError("Price multiplier cannot exceed 10.0")
        return value
    
    def validate_estimated_delivery_hours(self, value):
        if value > 120:  # 5 days
            raise serializers.ValidationError("Estimated delivery cannot exceed 120 hours (5 days)")
        return value


class LocationPricingSerializer(serializers.ModelSerializer):
    """
    Serializer for LocationPricing model
    """

    class Meta:
        model = LocationPricing
        fields = [
            'id',
            'city',
            'state',
            'area_type',
            'base_price',
            'price_multiplier',
            'is_active',
        ]
        read_only_fields = ['id']
    
    def validate_base_price(self, value):
        if value > Decimal('100.00'):
            raise serializers.ValidationError("Base price cannot exceed NPR 100")
        return value
    
    def validate_price_multiplier(self, value):
        if value < Decimal('0.1'):
            raise serializers.ValidationError("Price multiplier cannot be less than 0.1")
        if value > Decimal('5.0'):
            raise serializers.ValidationError("Price multiplier cannot exceed 5.0")
        return value
    
    def validate(self, data):
        city = data.get('city', '').strip().lower()
        state = data.get('state', '').strip().lower()
        
        if not city or not state:
            raise serializers.ValidationError("City and state cannot be empty")
        
        # Update with cleaned values
        data['city'] = city
        data['state'] = state
        
        return data

class PriceEstimationSerializer(serializers.Serializer):
    """
    Serializer for price estimation request
    """
    # Package details
    package_type = serializers.ChoiceField(choices=WeightSlab.PackageType.choices)
    weight = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01')
    )
    quantity = serializers.IntegerField(
        min_value=1,
        default=1,
        required=False
    )
    length = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=False,
        allow_null=True
    )
    width = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=False,
        allow_null=True
    )
    height = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=False,
        allow_null=True
    )
    
    # Location details
    pickup_city = serializers.CharField(max_length=100)
    pickup_state = serializers.CharField(max_length=100)
    delivery_city = serializers.CharField(max_length=100)
    delivery_state = serializers.CharField(max_length=100)
    
    # Service type
    service_type = serializers.ChoiceField(choices=ServiceTypePricing.ServiceType.choices)
    
    def validate(self, data):
        # Validate weight based on service type
        weight = data.get('weight')
        quantity = data.get('quantity', 1)
        service_type = data.get('service_type')
        
        # Calculate total weight
        total_weight = weight * quantity
        
        if service_type == 'express':
            if total_weight > 25:
                raise serializers.ValidationError(
                    {"weight": f"Express delivery cannot exceed 25 kg (you have {total_weight} kg with quantity {quantity})"}
                )
        elif service_type == 'standard':
            if total_weight > 50:
                raise serializers.ValidationError(
                    {"weight": f"Standard delivery cannot exceed 50 kg (you have {total_weight} kg with quantity {quantity})"}
                )
        
        # Validate pickup location exists
        pickup_city = data.get('pickup_city', '').strip().lower()
        pickup_state = data.get('pickup_state', '').strip().lower()
        
        if not LocationPricing.objects.filter(
            city__iexact=pickup_city,
            state__iexact=pickup_state,
            is_active=True
        ).exists():
            raise serializers.ValidationError(
                {"pickup_location": f"Pickup location '{pickup_city}, {pickup_state}' is not available"}
            )
        
        # Validate delivery location exists
        delivery_city = data.get('delivery_city', '').strip()
        delivery_state = data.get('delivery_state', '').strip()
        
        if not LocationPricing.objects.filter(
            city__iexact=delivery_city,
            state__iexact=delivery_state,
            is_active=True
        ).exists():
            raise serializers.ValidationError(
                {"delivery_location": f"Delivery location '{delivery_city}, {delivery_state}' is not available"}
            )
        
        # Validate same pickup and delivery location
        if (pickup_city == delivery_city and 
            pickup_state == delivery_state):
            raise serializers.ValidationError(
                "Pickup and delivery locations cannot be the same"
            )
        
        # Validate service type exists
        service_type = data.get('service_type')
        if not ServiceTypePricing.objects.filter(
            service_type=service_type,
            is_active=True
        ).exists():
            raise serializers.ValidationError(
                {"service_type": f"Service type '{service_type}' is not available"}
            )
        
        # Validate weight slab exists for package type
        package_type = data.get('package_type')
        weight = data.get('weight')
        quantity = data.get('quantity', 1)
        total_weight = weight * quantity
        
        if not WeightSlab.objects.filter(
            package_type=package_type,
            up_to_weight__gte=total_weight,
            is_active=True
        ).exists():
            raise serializers.ValidationError(
                {"weight": f"No weight slab available for {package_type} with total weight {total_weight} kg"}
            )
        
        # Validate dimensions if provided
        length = data.get('length')
        width = data.get('width')
        height = data.get('height')
        
        if length and length > 250:
            raise serializers.ValidationError(
                {"length": "Length cannot exceed 250 cm"}
            )
        
        if width and width > 250:
            raise serializers.ValidationError(
                {"width": "Width cannot exceed 250 cm"}
            )
        
        if height and height > 250:
            raise serializers.ValidationError(
                {"height": "Height cannot exceed 250 cm"}
            )
        
        return data

class LocationListSerializer(serializers.Serializer):
    """
    Serializer for location dropdown/autocomplete
    """
    city = serializers.CharField()
    state = serializers.CharField()