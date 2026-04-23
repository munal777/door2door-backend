from rest_framework import serializers

from ..models import OrderTracking
from myproject.utils import format_datetime


class OrderTrackingSerializer(serializers.ModelSerializer):
    """
    Serializer for order tracking history
    """
    created_at = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderTracking
        fields = [
            'id',
            'status',
            'location_city',
            'remarks',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_created_at(self, obj):
        return format_datetime(obj.created_at)


class PublicOrderTrackingSerializer(serializers.ModelSerializer):
    """Public-facing order tracking for customers"""
    status = serializers.CharField(source='get_status_display', read_only=True)
    created_at = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderTracking
        fields = [
            'status',
            'location_city',
            'remarks',
            'created_at'
        ]
    
    def get_created_at(self, obj):
        return format_datetime(obj.created_at)
