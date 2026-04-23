from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class Transaction(models.Model):
    
    class STATUS_CHOICES(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        SUCCESS = "SUCCESS", _("Success")
        FAILED = "FAILED", _("Failed")
        REFUNDED = "REFUNDED", _("Refunded")
        EXPIRED = "EXPIRED", _("Expired")  # Added for timeout scenarios

    class PROVIDERS(models.TextChoices):
        ESEWA = "esewa", _("eSewa")
        KHALTI = "khalti", _("Khalti")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    transaction_uuid = models.CharField(max_length=100, unique=True, db_index=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    service_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="NPR")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES.choices, default=STATUS_CHOICES.PENDING, db_index=True)

    # Provider info
    provider = models.CharField(max_length=20, choices=PROVIDERS.choices, db_index=True)
    provider_reference = models.CharField(max_length=200, blank=True, help_text="Transaction ID returned from payment gateway")
    metadata = models.JSONField(default=dict, blank=True)


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        
    def __str__(self):
        return f"{self.provider.upper()} - {self.status} - {self.total_amount} {self.currency}"