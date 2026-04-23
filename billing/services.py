from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Invoice


TWOPLACES = Decimal('0.01')


class InvoiceService:
    """Service layer for creating invoices."""

    @classmethod
    @transaction.atomic
    def create_invoice_for_confirmed_order(cls, order):
        """
        Idempotently create an invoice for a confirmed order.
        """
        if order.status != order.OrderStatus.CONFIRMED or not order.courier_provider_id:
            return None

        if hasattr(order, 'invoice'):
            return order.invoice

        invoice, _ = Invoice.objects.get_or_create(
            order=order,
            defaults={
                'courier_provider': order.courier_provider,
                'currency': 'NPR',
                'issue_date': timezone.localdate(),
                'total_amount': order.total_price,
            },
        )
        return invoice