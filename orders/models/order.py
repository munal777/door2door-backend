from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from decimal import Decimal


class Order(models.Model):
    """
    Main order model for both manual and online orders
    """
    class PackageType(models.TextChoices):
        DOCUMENT = 'document', _('Document')
        PACKAGE = 'package', _('Package')
    
    class ServiceType(models.TextChoices):
        STANDARD = 'standard', _('Standard')
        EXPRESS = 'express', _('Express')
    
    class OrderType(models.TextChoices):
        MANUAL = 'manual', _('Manual Order')
        ONLINE = 'online', _('Online Order')

    class OrderStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        CONFIRMED = 'confirmed', _('Confirmed')
        PICKUP_ASSIGNED = 'pickup_assigned', _('Pickup Assigned')
        PICKED_UP = 'picked_up', _('Picked Up')
        AT_ORIGIN_HUB = 'at_origin_hub', _('At Origin Hub')
        IN_TRANSIT = 'in_transit', _('In Transit')
        AT_DESTINATION_HUB = 'at_destination_hub', _('At Destination Hub')
        OUT_FOR_DELIVERY = 'out_for_delivery', _('Out for Delivery')
        DELIVERED = 'delivered', _('Delivered')
        CANCELLED = 'cancelled', _('Cancelled')
        RETURNED = 'returned', _('Returned')

    class PaymentMethod(models.TextChoices):
        COD = 'cod', _('Cash on Delivery')
        ESEWA = 'esewa', _('eSewa')
        SENDER_PREPAID = 'sender_prepaid', _('Sender Prepaid')

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PAID = 'paid', _('Paid')
        FAILED = 'failed', _('Failed')
        REFUNDED = 'refunded', _('Refunded')

    # Order Identification
    order_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True,
        help_text=_('Unique order number used for tracking and QR code generation')
    )
    
    order_type = models.CharField(max_length=20, choices=OrderType.choices)
    order_request = models.OneToOneField(
        'OrderRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order'
    )
    
    # Customer Information (only for online orders)
    consumer = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        help_text=_('Required for online orders, not needed for manual orders')
    )
    
    # Sender Details (Pickup Information)
    sender_name = models.CharField(max_length=200)
    sender_phone = models.CharField(max_length=20)
    sender_email = models.EmailField(blank=True)
    sender_address = models.TextField()
    sender_city = models.CharField(max_length=100)
    sender_state = models.CharField(max_length=100)
    sender_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    sender_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    
    # Receiver Details (Delivery Information)
    receiver_name = models.CharField(max_length=200)
    receiver_phone = models.CharField(max_length=20)
    receiver_email = models.EmailField(blank=True)
    receiver_address = models.TextField()
    receiver_city = models.CharField(max_length=100)
    receiver_state = models.CharField(max_length=100)
    receiver_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    receiver_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    
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
    length = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    width = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    height = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    package_description = models.TextField(blank=True)
    
    # Service Type
    service_type = models.CharField(
        max_length=20,
        choices=ServiceType.choices
    )
    estimated_delivery_hours = models.IntegerField(default=48)
    
    # Price
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Payment
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )

    # Courier
    courier_provider = models.ForeignKey(
        'accounts.CourierProvider',
        on_delete=models.PROTECT,
        related_name='orders'
    )
    
    # Order Status
    status = models.CharField(
        max_length=30,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING
    )
    
    # notes
    cancellation_reason = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Created by (for manual orders - tracks which staff member created the order)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_orders',
    )
    
    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['courier_provider', 'status']),
            models.Index(fields=['order_number']),
        ]

    def __str__(self):
        return f"Order {self.order_number} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_order_number():
        """Generate unique order number: MMDD + 5 random digits"""
        import random
        today = timezone.now().strftime('%m%d')
        random_digits = str(random.randint(10000, 99999))
        return f"{today}{random_digits}"

    @property
    def is_online_order(self):
        return self.order_type == self.OrderType.ONLINE

    @property
    def is_paid(self):
        return self.payment_status == self.PaymentStatus.PAID
