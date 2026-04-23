from django.db import models

from .order import Order


class OrderTracking(models.Model):
    """
    Order status tracking history
    Records every status change with timestamp and location
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='tracking_history'
    )
    location_city = models.CharField(max_length=50)
    status = models.CharField(max_length=30, choices=Order.OrderStatus.choices)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta: 
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', 'created_at']),
            models.Index(fields=['location_city']),
        ]

    def __str__(self):
        return f"{self.order.order_number} - {self.status} at {self.created_at}"
