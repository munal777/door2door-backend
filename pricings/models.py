from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


class WeightSlab(models.Model):
    """
    Weight and dimension-based pricing slabs with package types
    """
    class PackageType(models.TextChoices):
        DOCUMENT = 'document', _('Document')
        PACKAGE = 'package', _('Package')

    package_type = models.CharField(
        max_length=20,
        choices=PackageType.choices,
    )
    up_to_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    # Dimensional constraints (optional)
    length = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    width = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    height = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    extra_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    is_active = models.BooleanField(default=True, verbose_name=_('is active'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('created at'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('updated at'))

    class Meta:
        ordering = ['package_type', 'up_to_weight']
        unique_together = [['package_type', 'up_to_weight']]

    def __str__(self):
        return f"{self.get_package_type_display()} - Up to {self.up_to_weight} kg"

    @property
    def volume(self):
        """Calculate package volume in cubic cm"""
        if self.length and self.width and self.height:
            return self.length * self.width * self.height
        return None

    def validate_dimensions(self, user_length, user_width, user_height):
        """Validate dimensions based on total volume instead of individual sides"""
        if not (self.length and self.width and self.height):
            return True  # No dimension limits set
        
        if not (user_length and user_width and user_height):
            return True  # User didn't provide dimensions
        
        # Calculate volumes
        slab_volume = self.volume  # length × width × height
        user_volume = user_length * user_width * user_height
        
        # Check if user's volume is within the slab's volume limit
        return user_volume <= slab_volume


class ServiceTypePricing(models.Model):
    """
    Pricing for different service types
    """
    class ServiceType(models.TextChoices):
        STANDARD = 'standard', _('Standard Delivery')
        EXPRESS = 'express', _('Express Delivery')

    service_type = models.CharField(
        max_length=20,
        choices=ServiceType.choices,
        unique=True,
    )
    estimated_delivery_hours = models.IntegerField(
        validators=[MinValueValidator(1)]
    )
    price_multiplier = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    is_active = models.BooleanField(default=True, verbose_name=_('is active'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('created at'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('updated at'))

    def clean(self):
        if self.service_type:
            qs = ServiceTypePricing.objects.filter(service_type=self.service_type)
            if self.pk:
                qs = qs.exclude(pk=self.pk)  # exclude self on update
            if qs.exists():
                raise ValidationError({
                    'service_type': _(
                        f'A pricing entry for "{self.get_service_type_display()}" already exists.'
                    )
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_service_type_display()} - {self.price_multiplier}x"


class LocationPricing(models.Model):
    """
    Location model with pricing for Nepal market
    """
    class AreaType(models.TextChoices):
        CITY = 'city', _('City')
        REGIONAL = 'regional', _('Regional')

    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    area_type = models.CharField(
        max_length=20,
        choices=AreaType.choices,
        default=AreaType.CITY,
    )
    # Pricing fields
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    price_multiplier = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    is_active = models.BooleanField(default=True, verbose_name=_('is active'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('created at'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('updated at'))

    class Meta:
        ordering = ['state', 'city']
        unique_together = [['city', 'state']]

    def __str__(self):
        return f"{self.city}, {self.state}"

