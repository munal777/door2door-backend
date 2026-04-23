from rest_framework import serializers
from orders.models import Order


class EsewaPaymentInitSerializer(serializers.Serializer):
    """Serializer for initializing eSewa payment"""
    
    order_number = serializers.CharField(max_length=50, required=True)

    def validate_order_number(self, value):
        """Validate that order exists"""
        if not Order.objects.filter(order_number=value).exists():
            raise serializers.ValidationError("Order not found")
        
        return value
