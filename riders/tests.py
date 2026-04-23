from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CourierProvider, Rider
from riders.serializers import RiderLiveLocationUpdateSerializer


User = get_user_model()


class RiderLiveLocationUpdateSerializerTests(TestCase):
	def test_rejects_latitude_out_of_range(self):
		serializer = RiderLiveLocationUpdateSerializer(
			data={
				'latitude': 91,
				'longitude': 85,
			}
		)

		self.assertFalse(serializer.is_valid())
		self.assertIn('latitude', serializer.errors)


class RiderAppProfileAndAvailabilityApiTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.courier = CourierProvider.objects.create(
			name='Rider Courier',
			company_email='rider-courier@example.com',
			company_phone='9800000000',
			address_line='Kathmandu',
			city='Kathmandu',
			state='Bagmati',
			postal_code='44600',
			country='Nepal',
		)

		self.rider_user = User.objects.create_user(
			email='rider@example.com',
			password='password123',
			first_name='Rider',
			last_name='User',
			phone_number='9801111111',
			user_type=User.UserType.RIDER,
		)
		self.rider = Rider.objects.create(
			user=self.rider_user,
			company=self.courier,
			vehicle_type=Rider.VehicleType.BIKE,
			vehicle_number='BA-1-PA-1234',
			operational_status=Rider.OperationalStatus.ACTIVE,
			availability_status=Rider.AvailabilityStatus.OFFLINE,
		)

		self.non_rider_user = User.objects.create_user(
			email='consumer@example.com',
			password='password123',
			user_type=User.UserType.CONSUMER,
		)

	def test_get_rider_app_profile_success(self):
		self.client.force_authenticate(user=self.rider_user)
		response = self.client.get('/api/riders/app/profile/')

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.data['IsSuccess'])
		self.assertEqual(response.data['Result']['email'], 'rider@example.com')

	def test_patch_rider_app_profile_success(self):
		self.client.force_authenticate(user=self.rider_user)
		response = self.client.patch(
			'/api/riders/app/profile/',
			{
				'emergency_contact_name': 'Emergency Contact',
				'emergency_contact_phone': '9802222222',
				'vehicle_model': 'Pulsar',
			},
			format='json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.data['IsSuccess'])
		self.rider.refresh_from_db()
		self.assertEqual(self.rider.emergency_contact_name, 'Emergency Contact')
		self.assertEqual(self.rider.vehicle_model, 'Pulsar')

	def test_update_availability_success(self):
		self.client.force_authenticate(user=self.rider_user)
		response = self.client.post(
			'/api/riders/app/availability/',
			{'status': Rider.AvailabilityStatus.AVAILABLE},
			format='json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.data['IsSuccess'])
		self.assertEqual(response.data['Result']['status'], Rider.AvailabilityStatus.AVAILABLE)

		self.rider.refresh_from_db()
		self.assertEqual(self.rider.availability_status, Rider.AvailabilityStatus.AVAILABLE)

	def test_update_availability_rejects_non_active_rider(self):
		self.rider.operational_status = Rider.OperationalStatus.UNDER_REVIEW
		self.rider.save(update_fields=['operational_status', 'updated_at'])

		self.client.force_authenticate(user=self.rider_user)
		response = self.client.post(
			'/api/riders/app/availability/',
			{'status': Rider.AvailabilityStatus.AVAILABLE},
			format='json',
		)

		self.assertEqual(response.status_code, 403)
		self.assertFalse(response.data['IsSuccess'])

	def test_rider_app_profile_forbidden_for_non_rider(self):
		self.client.force_authenticate(user=self.non_rider_user)
		response = self.client.get('/api/riders/app/profile/')

		self.assertEqual(response.status_code, 403)
