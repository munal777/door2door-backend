from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import CourierProvider
from billing.services import InvoiceService
from orders.models import Order


User = get_user_model()


class InvoiceServiceTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email="invoice-user@example.com",
			password="password123",
		)
		self.courier = CourierProvider.objects.create(
			name="Invoice Courier",
			company_email="invoice-courier@example.com",
			company_phone="9800000000",
			address_line="Kathmandu",
			city="Kathmandu",
			state="Bagmati",
			postal_code="44600",
			country="Nepal",
		)

	def _create_order(self, status=Order.OrderStatus.CONFIRMED):
		return Order.objects.create(
			order_type=Order.OrderType.MANUAL,
			sender_name="Sender",
			sender_phone="9800000001",
			sender_address="Sender Address",
			sender_city="Kathmandu",
			sender_state="Bagmati",
			receiver_name="Receiver",
			receiver_phone="9800000002",
			receiver_address="Receiver Address",
			receiver_city="Pokhara",
			receiver_state="Gandaki",
			package_type=Order.PackageType.DOCUMENT,
			weight=Decimal("1.00"),
			service_type=Order.ServiceType.STANDARD,
			total_price=Decimal("300.00"),
			payment_method=Order.PaymentMethod.COD,
			courier_provider=self.courier,
			status=status,
			created_by=self.user,
		)

	def test_create_invoice_for_confirmed_order_creates_invoice(self):
		order = self._create_order(status=Order.OrderStatus.CONFIRMED)

		invoice = InvoiceService.create_invoice_for_confirmed_order(order)

		self.assertIsNotNone(invoice)
		self.assertEqual(invoice.order_id, order.id)
		self.assertEqual(invoice.courier_provider_id, self.courier.id)
		self.assertEqual(invoice.currency, "NPR")
		self.assertEqual(invoice.total_amount, order.total_price)