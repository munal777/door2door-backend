import os
from django.utils import timezone
from django.db import models
from django.core.validators import FileExtensionValidator

from .order import Order


def pod_upload_path(instance, filename):
    """Organise POD images by date: media/pod/YYYY/MM/DD/<order_number>_<filename>"""
    today = timezone.now()
    ext = os.path.splitext(filename)[1].lower()
    safe_name = f"{instance.order.order_number}{ext}"
    return f"pod/{today.year}/{today.month:02d}/{today.day:02d}/{safe_name}"


class ProofOfDelivery(models.Model):
    """
    Stores delivery proof (photograph) captured by the rider at delivery time.
    Exactly one POD record is allowed per order (OneToOneField).
    The record is created *before* the order status is set to DELIVERED —
    the status update endpoint checks for its existence as a gate.
    """

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='proof_of_delivery',
        help_text='The order this proof belongs to.'
    )
    image = models.ImageField(
        upload_to=pod_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
        help_text='Delivery proof photo captured by the rider.'
    )
    uploaded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_pods',
        help_text='The rider who uploaded this proof.'
    )
    notes = models.TextField(
        blank=True,
        help_text='Optional notes from the rider about the delivery.'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_proof_of_delivery'
        verbose_name = 'Proof of Delivery'
        verbose_name_plural = 'Proofs of Delivery'

    def __str__(self):
        return f"POD for Order {self.order.order_number}"
