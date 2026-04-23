import random

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class TransportBucket(models.Model):
    """
    Union Bucket/Manifest for grouping orders on same route.
    """
    # Bucket Identification
    bucket_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True,
        help_text=_('Unique bucket tracking code for QR scanning')
    )
    
    # Route Information - Multi-stop support via BucketStop model
    origin_city = models.CharField(
        max_length=100,
        help_text=_('Starting city for this bucket route')
    )
    origin_state = models.CharField(max_length=100)
    
    # Courier Provider
    courier_provider = models.ForeignKey(
        'accounts.CourierProvider',
        on_delete=models.PROTECT,
        related_name='transport_buckets'
    )
    
    # Metadata
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_buckets'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['courier_provider', 'created_at']),
            models.Index(fields=['origin_city', 'origin_state', 'created_at']),
        ]
    
    def __str__(self):
        return f"Bucket {self.bucket_number} from {self.origin_city}"
    
    def save(self, *args, **kwargs):
        if not self.bucket_number:
            self.bucket_number = self.generate_bucket_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_bucket_number():
        """Generate unique 8-digit bucket number: MMDD + 4 random digits"""
        today = timezone.now().strftime('%m%d')
        random_digits = str(random.randint(1000, 9999))
        return f"{random_digits}{today}"
    
    @property
    def order_count(self):
        """Get number of orders currently in this bucket"""
        return self.bucket_orders.count()


class BucketStop(models.Model):
    """
    Defines multi-stop route for a bucket.
    """
    bucket = models.ForeignKey(
        TransportBucket,
        on_delete=models.CASCADE,
        related_name="stops"
    )
    city = models.CharField(
        max_length=100,
        help_text=_('City at this stop')
    )
    state = models.CharField(
        max_length=100,
        help_text=_('State of this stop')
    )
    stop_order = models.PositiveIntegerField(
        help_text=_('Sequence: 1=first stop, 2=second stop, etc.')
    )
    
    class Meta:
        ordering = ['bucket', 'stop_order']
        indexes = [
            models.Index(fields=['bucket', 'stop_order']),
            models.Index(fields=['city', 'state']),
        ]
    
    def __str__(self):
        return f"{self.bucket.bucket_number} - Stop {self.stop_order}: {self.city}"
    
    @property
    def orders_for_this_stop(self):
        """Get orders that should be unloaded at this city"""
        return self.bucket.bucket_orders.filter(
            order__receiver_city__iexact=self.city
        )



class BucketOrder(models.Model):
    bucket = models.ForeignKey(TransportBucket, on_delete=models.CASCADE, related_name='bucket_orders')
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='bucket_links')
    added_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loaded_orders'
    )

    class Meta:
        unique_together = ('bucket', 'order')
        indexes = [
            models.Index(fields=['bucket']),
            models.Index(fields=['order']),
        ]

    def __str__(self):
        return f"{self.order.order_number} in {self.bucket.bucket_number}"




class BucketTracking(models.Model):
    """ 
    Transport Bucket status tracking with explicit action types for different journey stages.
    """
    class ScanAction(models.TextChoices):
        DEPARTED_ORIGIN = 'departed_origin', _('Departed from Origin Hub')
        ARRIVED_TRANSIT = 'arrived_transit', _('Arrived at Transit Hub')
        DEPARTED_TRANSIT = 'departed_transit', _('Departed from Transit Hub')
        ARRIVED_DESTINATION = 'arrived_destination', _('Arrived at Destination Hub')
        PARTIAL_UNLOAD = 'partial_unload', _('Partial Unload at Stop')
    
    bucket = models.ForeignKey(
        TransportBucket,
        on_delete=models.CASCADE,
        related_name='tracking_history'
    )
    action = models.CharField(
        max_length=20,
        choices=ScanAction.choices
    )
    location_city = models.CharField(
        max_length=100,
        help_text=_('City where scan occurred')
    )
    bucket_stop = models.ForeignKey(
        BucketStop,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tracking_events',
        help_text=_('Related bucket stop if applicable')
    )
    scanned_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bucket_scans'
    )
    orders_updated_count = models.IntegerField(
        default=0,
        help_text=_('Number of orders updated by this scan')
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['bucket', 'created_at']),
            models.Index(fields=['location_city', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.bucket.bucket_number} - {self.get_action_display()} at {self.location_city}"
