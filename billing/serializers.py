from rest_framework import serializers

from myproject.utils import format_datetime
from .models import Invoice


class InvoiceListSerializer(serializers.ModelSerializer):
    created_at = serializers.SerializerMethodField()
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    total_quantity = serializers.IntegerField(source='order.total_quantity', read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'invoice_number',
            'status',
            'order',
            'order_number',
            'total_quantity',
            'currency',
            'total_amount',
            'issue_date',
            'created_at',
        ]

    def get_created_at(self, obj):
        return format_datetime(obj.created_at)


class InvoiceDetailSerializer(serializers.ModelSerializer):
    courier_provider_name = serializers.CharField(source='courier_provider.name', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    
    sender_name = serializers.CharField(source='order.sender_name', read_only=True)
    sender_phone = serializers.CharField(source='order.sender_phone', read_only=True)
    sender_address = serializers.CharField(source='order.sender_address', read_only=True)
    sender_city = serializers.CharField(source='order.sender_city', read_only=True)
    
    receiver_name = serializers.CharField(source='order.receiver_name', read_only=True)
    receiver_phone = serializers.CharField(source='order.receiver_phone', read_only=True)
    receiver_address = serializers.CharField(source='order.receiver_address', read_only=True)
    receiver_city = serializers.CharField(source='order.receiver_city', read_only=True)

    total_quantity = serializers.IntegerField(source='order.total_quantity', read_only=True)
    
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'invoice_number',
            'status',
            'courier_provider_name',
            'order_number',
            'sender_name',
            'sender_phone',
            'sender_address',
            'sender_city',
            'receiver_name',
            'receiver_phone',
            'receiver_address',
            'receiver_city',
            'total_quantity',
            'currency',
            'total_amount',
            'issue_date',
            'created_at',
            'updated_at',
        ]

    def get_created_at(self, obj):
        return format_datetime(obj.created_at)

    def get_updated_at(self, obj):
        return format_datetime(obj.updated_at)
