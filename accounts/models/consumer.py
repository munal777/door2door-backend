from django.db import models
from django.utils.translation import gettext_lazy as _

from .user import User


class Address(models.Model):
    """
    Saved Addresses for Users.
    
    Stores delivery addresses for users. Consumers can save multiple addresses
    (home, work, etc.) for quick selection when placing orders.
    """
    
    class AddressType(models.TextChoices):
        """Predefined address types"""
        HOME = "home", _("Home")
        WORK = "work", _("Work")
        OTHER = "other", _("Other")
    
    # Relationship
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='addresses',
        help_text=_("User who owns this address")
    )
    
    # Address Type & Label
    label = models.CharField(
        max_length=50,
        choices=AddressType.choices,
        default=AddressType.OTHER,
        help_text=_("Address category")
    )
    
    # Address Details
    address_line = models.TextField(
        help_text=_("Street address, building name, floor, etc.")
    )
    landmark = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Nearby landmark for easier location")
    )
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    
    # GPS Coordinates
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        help_text=_("GPS latitude for precise location")
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        help_text=_("GPS longitude for precise location")
    )
    
    # Settings
    is_default = models.BooleanField(
        default=False,
        help_text=_("Mark as default address for quick access")
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Address")
        verbose_name_plural = _("Addresses")
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_default']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.get_label_display()}"

    def save(self, *args, **kwargs):
        """
        Override save to ensure only one default address per user.
        """
        if self.is_default:
            # Set all other addresses of this user to non-default
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    @property
    def full_address(self):
        """Get formatted full address"""
        parts = [
            self.address_line,
            self.landmark,
            self.city,
            self.state,
        ]
        return ", ".join(filter(None, parts))