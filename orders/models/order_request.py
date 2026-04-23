import random

from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from decimal import Decimal


class OrderRequest(models.Model):
    """
    Online order requests sent from consumer app
    Pending requests waiting for courier acceptance
    """
    class PackageType(models.TextChoices):
        DOCUMENT = 'document', _('Document')
        PACKAGE = 'package', _('Package')
    
    class ServiceType(models.TextChoices):
        STANDARD = 'standard', _('Standard')
        EXPRESS = 'express', _('Express')
    
    class RequestStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        ACCEPTED = 'accepted', _('Accepted')
        REJECTED = 'rejected', _('Rejected')
        EXPIRED = 'expired', _('Expired')

    class PaymentMethod(models.TextChoices):
        COD = 'cod', _('Cash on Delivery')
        ESEWA = 'esewa', _('eSewa')
        SENDER_PREPAID = 'sender_prepaid', _('Sender Prepaid')

    request_number = models.CharField(max_length=50, unique=True, editable=False)
    consumer = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='order_requests'
    )
    
    # Pickup Details
    pickup_name = models.CharField(max_length=200)
    pickup_phone = models.CharField(max_length=20)
    pickup_address = models.TextField()
    pickup_city = models.CharField(max_length=100)
    pickup_state = models.CharField(max_length=100)
    pickup_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Delivery Details
    delivery_name = models.CharField(max_length=200)
    delivery_phone = models.CharField(max_length=20)
    delivery_address = models.TextField()
    delivery_city = models.CharField(max_length=100)
    delivery_state = models.CharField(max_length=100)
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Package Details
    package_type = models.CharField(
        max_length=20,
        choices=PackageType.choices
    )
    weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    total_quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text=_(
            'Total quantity of items inside this parcel (single number used for invoices).'
        ),
    )
    length = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    width = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    package_description = models.TextField(blank=True)
    
    # Service & Pricing
    service_type = models.CharField(
        max_length=20,
        choices=ServiceType.choices
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.COD,
    )
    estimated_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    
    # Request Status
    status = models.CharField(
        max_length=20,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING
    )
    accepted_by = models.ForeignKey(
        'accounts.CourierProvider',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accepted_requests'
    )
    rejection_reason = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'order_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['consumer', 'status']),
        ]

    def __str__(self):
        return f"Request {self.request_number} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = self.generate_request_number()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_request_number():
        """Generate unique 12-digit request number: MMDD + 4 random digits"""
        import random
        today = timezone.now().strftime('%m%d')
        random_digits = str(random.randint(1000, 9999))
        return f"{today}{random_digits}"


class OrderRequestCourierResponse(models.Model):
    """
    Courier-specific response to a nearby order request.
    Decline/ignore are personal actions and should not affect other couriers.
    """
    class ResponseType(models.TextChoices):
        DECLINED = 'declined', _('Declined')
        IGNORED = 'ignored', _('Ignored')

    order_request = models.ForeignKey(
        OrderRequest,
        on_delete=models.CASCADE,
        related_name='courier_responses'
    )
    courier_provider = models.ForeignKey(
        'accounts.CourierProvider',
        on_delete=models.CASCADE,
        related_name='order_request_responses'
    )
    response_type = models.CharField(max_length=20, choices=ResponseType.choices)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'order_request_courier_responses'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['order_request', 'courier_provider'],
                name='unique_order_request_courier_response',
            ),
        ]
        indexes = [
            models.Index(fields=['courier_provider', 'response_type']),
            models.Index(fields=['order_request', 'response_type']),
        ]

    def __str__(self):
        return f"{self.order_request.request_number} - {self.courier_provider.name} - {self.response_type}"
