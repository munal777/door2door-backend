from django.db.models.signals import post_save
from django.dispatch import receiver

from orders.models import Order

from .services import InvoiceService


@receiver(post_save, sender=Order)
def create_invoice_on_order_confirmation(sender, instance, **kwargs):
    """
    Generate invoice when an order is confirmed.
    Safe to run repeatedly because InvoiceService is idempotent.
    """
    if instance.status == Order.OrderStatus.CONFIRMED:
        InvoiceService.create_invoice_for_confirmed_order(instance)
