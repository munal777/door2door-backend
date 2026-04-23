from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import CourierProvider
from orders.models import BucketOrder, Order, TransportBucket
from orders.serializers import ManualOrderCreateSerializer


User = get_user_model()


class OrderModelTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email="order-user@example.com",
			password="password123",
		)
		self.courier = CourierProvider.objects.create(
			name="Order Courier",
			company_email="order-courier@example.com",
			company_phone="9822222222",
			address_line="Kathmandu",
			city="Kathmandu",
			state="Bagmati",
			postal_code="44600",
			country="Nepal",
		)

	def _create_order(self, **overrides):
		defaults = {
			"order_type": Order.OrderType.MANUAL,
			"sender_name": "Sender",
			"sender_phone": "9822222223",
			"sender_address": "Sender Address",
			"sender_city": "Kathmandu",
			"sender_state": "Bagmati",
			"receiver_name": "Receiver",
			"receiver_phone": "9822222224",
			"receiver_address": "Receiver Address",
			"receiver_city": "Pokhara",
			"receiver_state": "Gandaki",
			"package_type": Order.PackageType.DOCUMENT,
			"weight": Decimal("1.00"),
			"service_type": Order.ServiceType.STANDARD,
			"total_price": Decimal("700.00"),
			"payment_method": Order.PaymentMethod.COD,
			"payment_status": Order.PaymentStatus.PENDING,
			"courier_provider": self.courier,
			"status": Order.OrderStatus.CONFIRMED,
			"created_by": self.user,
		}
		defaults.update(overrides)
		return Order.objects.create(**defaults)

	def test_save_auto_generates_order_number(self):
		order = self._create_order()

		self.assertTrue(order.order_number)
		self.assertEqual(len(order.order_number), 13)
		self.assertTrue(order.order_number.isdigit())

	def test_is_online_order_property(self):
		order = self._create_order(order_type=Order.OrderType.ONLINE)

		self.assertTrue(order.is_online_order)

	def test_is_paid_property(self):
		order = self._create_order(payment_status=Order.PaymentStatus.PAID)

		self.assertTrue(order.is_paid)


class TransportBucketModelTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email="bucket-user@example.com",
			password="password123",
		)
		self.courier = CourierProvider.objects.create(
			name="Bucket Courier",
			company_email="bucket-courier@example.com",
			company_phone="9833333333",
			address_line="Kathmandu",
			city="Kathmandu",
			state="Bagmati",
			postal_code="44600",
			country="Nepal",
		)

	def _create_order(self):
		return Order.objects.create(
			order_type=Order.OrderType.MANUAL,
			sender_name="Sender",
			sender_phone="9833333334",
			sender_address="Sender Address",
			sender_city="Kathmandu",
			sender_state="Bagmati",
			receiver_name="Receiver",
			receiver_phone="9833333335",
			receiver_address="Receiver Address",
			receiver_city="Pokhara",
			receiver_state="Gandaki",
			package_type=Order.PackageType.DOCUMENT,
			weight=Decimal("2.00"),
			service_type=Order.ServiceType.STANDARD,
			total_price=Decimal("800.00"),
			payment_method=Order.PaymentMethod.COD,
			courier_provider=self.courier,
			status=Order.OrderStatus.CONFIRMED,
			created_by=self.user,
		)

	def test_order_count_reflects_bucket_membership(self):
		bucket = TransportBucket.objects.create(
			origin_city="Kathmandu",
			origin_state="Bagmati",
			courier_provider=self.courier,
			created_by=self.user,
		)
		order = self._create_order()

		self.assertEqual(bucket.order_count, 0)

		BucketOrder.objects.create(bucket=bucket, order=order, added_by=self.user)

		self.assertEqual(bucket.order_count, 1)


class ManualOrderCreateValidationTests(TestCase):
	def _valid_payload(self, **overrides):
		payload = {
			"sender_name": "Alice",
			"sender_phone": "9801111111",
			"sender_email": "alice@example.com",
			"sender_address": "Kathmandu Street",
			"sender_city": "Kathmandu",
			"sender_state": "Bagmati",
			"receiver_name": "Bob",
			"receiver_phone": "9802222222",
			"receiver_email": "bob@example.com",
			"receiver_address": "Pokhara Street",
			"receiver_city": "Pokhara",
			"receiver_state": "Gandaki",
			"package_type": Order.PackageType.DOCUMENT,
			"weight": "10.00",
			"service_type": Order.ServiceType.STANDARD,
			"payment_method": Order.PaymentMethod.COD,
			"payment_status": Order.PaymentStatus.PENDING,
		}
		payload.update(overrides)
		return payload

	def test_validate_rejects_express_weight_above_limit(self):
		serializer = ManualOrderCreateSerializer(
			data=self._valid_payload(service_type=Order.ServiceType.EXPRESS, weight="25.01")
		)

		self.assertFalse(serializer.is_valid())
		self.assertIn("weight", serializer.errors)

	def test_validate_rejects_standard_weight_above_limit(self):
		serializer = ManualOrderCreateSerializer(
			data=self._valid_payload(service_type=Order.ServiceType.STANDARD, weight="50.01")
		)

		self.assertFalse(serializer.is_valid())
		self.assertIn("weight", serializer.errors)

	def test_validate_rejects_express_total_weight_above_limit_with_quantity(self):
		serializer = ManualOrderCreateSerializer(
			data=self._valid_payload(
				service_type=Order.ServiceType.EXPRESS,
				weight="10.00",
				total_quantity=3,
			)
		)

		self.assertFalse(serializer.is_valid())
		self.assertIn("weight", serializer.errors)

	def test_validate_rejects_standard_total_weight_above_limit_with_quantity(self):
		serializer = ManualOrderCreateSerializer(
			data=self._valid_payload(
				service_type=Order.ServiceType.STANDARD,
				weight="20.00",
				total_quantity=3,
			)
		)

		self.assertFalse(serializer.is_valid())
		self.assertIn("weight", serializer.errors)

	def test_validate_rejects_non_positive_weight(self):
		serializer = ManualOrderCreateSerializer(data=self._valid_payload(weight="0.00"))

		self.assertFalse(serializer.is_valid())
		self.assertIn("weight", serializer.errors)
		