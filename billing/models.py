import random

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Invoice(models.Model):
	"""
	Invoice generated for a single confirmed order handled by a courier provider.
	"""

	class InvoiceStatus(models.TextChoices):
		ISSUED = 'issued', _('Issued')
		PAID = 'paid', _('Paid')
		CANCELLED = 'cancelled', _('Cancelled')

	invoice_number = models.CharField(max_length=50, unique=True, editable=False, db_index=True)
	courier_provider = models.ForeignKey(
		'accounts.CourierProvider',
		on_delete=models.PROTECT,
		related_name='invoices',
	)
	order = models.OneToOneField(
		'orders.Order',
		on_delete=models.PROTECT,
		related_name='invoice',
	)

	status = models.CharField(
		max_length=20,
		choices=InvoiceStatus.choices,
		default=InvoiceStatus.ISSUED,
	)
	currency = models.CharField(max_length=10, default='NPR')

	# Final amount captured from order.total_price at invoice creation.
	total_amount = models.DecimalField(max_digits=10, decimal_places=2)

	issue_date = models.DateField(default=timezone.localdate)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['courier_provider', 'status']),
			models.Index(fields=['courier_provider', 'issue_date']),
			models.Index(fields=['created_at']),
		]

	def __str__(self):
		return f"{self.invoice_number} - {self.courier_provider.name}"

	def save(self, *args, **kwargs):
		if not self.invoice_number:
			self.invoice_number = self.generate_invoice_number()
		super().save(*args, **kwargs)

	@staticmethod
	def generate_invoice_number():
		date_part = timezone.now().strftime('%m%d')
		random_digits = str(random.randint(10000, 99999))
		return f"INV{date_part}{random_digits}"

