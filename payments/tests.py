from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import CourierProvider
from orders.models import Order
from payments.models import Transaction
from payments.services import PaymentService


User = get_user_model()


class PaymentServiceTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email="payment-user@example.com",
			password="password123",
		)
		self.courier = CourierProvider.objects.create(
			name="Payment Courier",
			company_email="payment-courier@example.com",
			company_phone="9811111111",
			address_line="Kathmandu",
			city="Kathmandu",
			state="Bagmati",
			postal_code="44600",
			country="Nepal",
		)
		self.order = Order.objects.create(
			order_type=Order.OrderType.MANUAL,
			sender_name="Sender",
			sender_phone="9811111112",
			sender_address="Sender Address",
			sender_city="Kathmandu",
			sender_state="Bagmati",
			receiver_name="Receiver",
			receiver_phone="9811111113",
			receiver_address="Receiver Address",
			receiver_city="Pokhara",
			receiver_state="Gandaki",
			package_type=Order.PackageType.DOCUMENT,
			weight=Decimal("1.00"),
			service_type=Order.ServiceType.STANDARD,
			total_price=Decimal("500.00"),
			payment_method=Order.PaymentMethod.COD,
			courier_provider=self.courier,
			status=Order.OrderStatus.CONFIRMED,
			created_by=self.user,
		)
		self.transaction = Transaction.objects.create(
			user=self.user,
			transaction_uuid="txn-uuid-001",
			total_amount=Decimal("500.00"),
			tax_amount=Decimal("0.00"),
			service_charge=Decimal("0.00"),
			currency="NPR",
			provider=Transaction.PROVIDERS.ESEWA,
			metadata={"order_number": self.order.order_number},
		)

	def test_handle_payment_completion_marks_order_paid(self):
		payment_data = {
			"transaction_code": "ESEWA-REF-001",
			"status": "COMPLETE",
		}

		result = PaymentService.handle_payment_completion(self.transaction, payment_data)

		self.transaction.refresh_from_db()
		self.order.refresh_from_db()

		self.assertTrue(result["success"])
		self.assertEqual(self.transaction.status, Transaction.STATUS_CHOICES.SUCCESS)
		self.assertEqual(self.transaction.provider_reference, "ESEWA-REF-001")
		self.assertEqual(self.order.payment_method, Order.PaymentMethod.ESEWA)
		self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)

	def test_handle_payment_completion_rejects_non_complete_status(self):
		payment_data = {
			"transaction_code": "ESEWA-REF-002",
			"status": "PENDING",
		}

		result = PaymentService.handle_payment_completion(self.transaction, payment_data)

		self.transaction.refresh_from_db()

		self.assertFalse(result["success"])
		self.assertEqual(self.transaction.status, Transaction.STATUS_CHOICES.PENDING)

	def test_handle_payment_failure_marks_transaction_failed(self):
		payment_data = {
			"status": "FAILED",
			"reason": "Bank timeout",
		}

		result = PaymentService.handle_payment_failure(
			self.transaction,
			payment_data,
			error_message="Gateway timeout",
		)

		self.transaction.refresh_from_db()

		self.assertFalse(result["success"])
		self.assertEqual(self.transaction.status, Transaction.STATUS_CHOICES.FAILED)
		self.assertEqual(self.transaction.metadata.get("error"), "Gateway timeout")
		self.assertEqual(self.transaction.metadata.get("payment_status"), "FAILED")

