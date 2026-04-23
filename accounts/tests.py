# """
# Test cases for Rider Registration System

# Run with: python manage.py test accounts.tests.test_rider_registration
# """

# from django.test import TestCase
# from django.contrib.auth import get_user_model
# from rest_framework.test import APITestCase, APIClient
# from rest_framework import status

# from accounts.models.provider import CourierProvider
# from accounts.models.rider import Rider

# User = get_user_model()


# class CourierRegistrationKeyTestCase(TestCase):
#     """Test courier registration key generation"""
    
#     def setUp(self):
#         self.courier = CourierProvider.objects.create(
#             name="Test Courier Co.",
#             company_email="test@courier.com",
#             company_phone="+9771234567890",
#             registration_number="REG123456",
#             address_line="Test Street",
#             city="Kathmandu",
#             state="Bagmati",
#             postal_code="44600",
#             country="Nepal"
#         )
    
#     def test_generate_registration_key(self):
#         """Test registration key generation"""
#         key = self.courier.generate_rider_registration_key()
        
#         self.assertIsNotNone(key)
#         self.assertEqual(len(key), 12)
#         self.assertEqual(key, self.courier.rider_registration_key)
        
#         # Verify it's stored in database
#         self.courier.refresh_from_db()
#         self.assertEqual(self.courier.rider_registration_key, key)
    
#     def test_registration_key_uniqueness(self):
#         """Test that registration keys are unique"""
#         courier1 = self.courier
#         courier2 = CourierProvider.objects.create(
#             name="Another Courier",
#             company_email="another@courier.com",
#             company_phone="+9779876543210",
#             registration_number="REG789012",
#             address_line="Another Street",
#             city="Pokhara",
#             state="Gandaki",
#             postal_code="33700",
#             country="Nepal"
#         )
        
#         key1 = courier1.generate_rider_registration_key()
#         key2 = courier2.generate_rider_registration_key()
        
#         self.assertNotEqual(key1, key2)
    
#     def test_regenerate_registration_key(self):
#         """Test key regeneration"""
#         old_key = self.courier.generate_rider_registration_key()
#         new_key = self.courier.regenerate_rider_registration_key()
        
#         self.assertNotEqual(old_key, new_key)
#         self.assertEqual(new_key, self.courier.rider_registration_key)


# class RiderRegistrationAPITestCase(APITestCase):
#     """Test rider registration API endpoints"""
    
#     def setUp(self):
#         self.client = APIClient()
        
#         # Create courier provider
#         self.courier = CourierProvider.objects.create(
#             name="Fast Delivery Co.",
#             company_email="fast@delivery.com",
#             company_phone="+9771234567890",
#             registration_number="REG123456",
#             address_line="Test Street",
#             city="Kathmandu",
#             state="Bagmati",
#             postal_code="44600",
#             country="Nepal",
#             is_active=True,
#             max_riders=50
#         )
        
#         # Generate registration key
#         self.registration_key = self.courier.generate_rider_registration_key()
        
#         # Valid rider data
#         self.rider_data = {
#             "registration_key": self.registration_key,
#             "email": "rider@example.com",
#             "password": "SecurePass123",
#             "password_confirm": "SecurePass123",
#             "phone_number": "+9779876543210",
#             "full_name": "John Doe",
#             "date_of_birth": "1995-05-15",
#             "license_number": "DL12345",
#             "vehicle_type": "bike",
#             "vehicle_number": "BA-1-PA-1234",
#             "vehicle_model": "Honda CB150",
#             "vehicle_color": "Red",
#             "emergency_contact_name": "Jane Doe",
#             "emergency_contact_phone": "+9779876543211"
#         }
    
#     def test_validate_registration_key_valid(self):
#         """Test validation of valid registration key"""
#         url = '/api/accounts/riders/validate-key/'
#         data = {'registration_key': self.registration_key}
        
#         response = self.client.post(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertTrue(response.data['valid'])
#         self.assertEqual(response.data['courier_name'], self.courier.name)
#         self.assertTrue(response.data['can_register'])
    
#     def test_validate_registration_key_invalid(self):
#         """Test validation of invalid registration key"""
#         url = '/api/accounts/riders/validate-key/'
#         data = {'registration_key': 'INVALIDKEY123'}
        
#         response = self.client.post(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
#         self.assertFalse(response.data['valid'])
    
#     def test_rider_registration_success(self):
#         """Test successful rider registration"""
#         url = '/api/accounts/riders/register/'
        
#         response = self.client.post(url, self.rider_data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)
#         self.assertIn('id', response.data)
#         self.assertEqual(response.data['user']['email'], self.rider_data['email'])
#         self.assertEqual(response.data['company']['name'], self.courier.name)
#         self.assertEqual(response.data['operational_status'], 'pending_documents')
        
#         # Verify user was created
#         user = User.objects.get(email=self.rider_data['email'])
#         self.assertEqual(user.user_type, User.UserType.RIDER)
        
#         # Verify rider profile was created
#         rider = Rider.objects.get(user=user)
#         self.assertEqual(rider.company, self.courier)
#         self.assertEqual(rider.vehicle_number, self.rider_data['vehicle_number'])
    
#     def test_rider_registration_invalid_key(self):
#         """Test registration with invalid key"""
#         url = '/api/accounts/riders/register/'
#         data = self.rider_data.copy()
#         data['registration_key'] = 'INVALIDKEY123'
        
#         response = self.client.post(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#         self.assertIn('registration_key', response.data)
    
#     def test_rider_registration_password_mismatch(self):
#         """Test registration with mismatched passwords"""
#         url = '/api/accounts/riders/register/'
#         data = self.rider_data.copy()
#         data['password_confirm'] = 'DifferentPassword'
        
#         response = self.client.post(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#         self.assertIn('password_confirm', response.data)
    
#     def test_rider_registration_duplicate_email(self):
#         """Test registration with duplicate email"""
#         url = '/api/accounts/riders/register/'
        
#         # First registration
#         self.client.post(url, self.rider_data, format='json')
        
#         # Second registration with same email
#         data = self.rider_data.copy()
#         data['phone_number'] = "+9779876543299"
#         data['vehicle_number'] = "BA-2-PA-5678"
        
#         response = self.client.post(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#         self.assertIn('email', response.data)
    
#     def test_rider_registration_duplicate_vehicle(self):
#         """Test registration with duplicate vehicle number"""
#         url = '/api/accounts/riders/register/'
        
#         # First registration
#         self.client.post(url, self.rider_data, format='json')
        
#         # Second registration with same vehicle
#         data = self.rider_data.copy()
#         data['email'] = "another@rider.com"
#         data['phone_number'] = "+9779876543299"
        
#         response = self.client.post(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#         self.assertIn('vehicle_number', response.data)
    
#     def test_rider_registration_age_validation(self):
#         """Test registration with invalid age"""
#         url = '/api/accounts/riders/register/'
#         data = self.rider_data.copy()
#         data['date_of_birth'] = "2010-01-01"  # Too young
        
#         response = self.client.post(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#         self.assertIn('date_of_birth', response.data)
    
#     def test_rider_registration_max_capacity(self):
#         """Test registration when courier reaches max capacity"""
#         # Set max riders to 1
#         self.courier.max_riders = 1
#         self.courier.save()
        
#         url = '/api/accounts/riders/register/'
        
#         # First registration should succeed
#         response1 = self.client.post(url, self.rider_data, format='json')
#         self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
#         # Second registration should fail
#         data2 = self.rider_data.copy()
#         data2['email'] = "rider2@example.com"
#         data2['phone_number'] = "+9779876543299"
#         data2['vehicle_number'] = "BA-2-PA-5678"
        
#         response2 = self.client.post(url, data2, format='json')
#         self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
#         self.assertIn('registration_key', response2.data)


# class RiderProfileAPITestCase(APITestCase):
#     """Test rider profile endpoints"""
    
#     def setUp(self):
#         self.client = APIClient()
        
#         # Create courier
#         self.courier = CourierProvider.objects.create(
#             name="Fast Delivery Co.",
#             company_email="fast@delivery.com",
#             company_phone="+9771234567890",
#             registration_number="REG123456",
#             address_line="Test Street",
#             city="Kathmandu",
#             state="Bagmati",
#             postal_code="44600",
#             is_active=True
#         )
        
#         # Create user and rider
#         self.user = User.objects.create_user(
#             email="rider@example.com",
#             password="password123",
#             phone_number="+9779876543210",
#             user_type=User.UserType.RIDER
#         )
        
#         self.rider = Rider.objects.create(
#             user=self.user,
#             company=self.courier,
#             full_name="John Doe",
#             license_number="DL12345",
#             vehicle_type="bike",
#             vehicle_number="BA-1-PA-1234",
#             operational_status=Rider.OperationalStatus.ACTIVE
#         )
    
#     def test_get_rider_profile_authenticated(self):
#         """Test retrieving rider profile when authenticated"""
#         self.client.force_authenticate(user=self.user)
#         url = '/api/accounts/riders/profile/'
        
#         response = self.client.get(url)
        
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response.data['full_name'], self.rider.full_name)
#         self.assertEqual(response.data['vehicle_number'], self.rider.vehicle_number)
    
#     def test_get_rider_profile_unauthenticated(self):
#         """Test retrieving rider profile when not authenticated"""
#         url = '/api/accounts/riders/profile/'
        
#         response = self.client.get(url)
        
#         self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
#     def test_update_rider_profile(self):
#         """Test updating rider profile"""
#         self.client.force_authenticate(user=self.user)
#         url = '/api/accounts/riders/profile/'
        
#         data = {
#             'emergency_contact_name': 'Jane Doe Updated',
#             'vehicle_color': 'Blue'
#         }
        
#         response = self.client.patch(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
        
#         # Verify changes
#         self.rider.refresh_from_db()
#         self.assertEqual(self.rider.emergency_contact_name, data['emergency_contact_name'])
#         self.assertEqual(self.rider.vehicle_color, data['vehicle_color'])
    
#     def test_update_availability_status(self):
#         """Test updating rider availability"""
#         self.client.force_authenticate(user=self.user)
#         url = '/api/accounts/riders/availability/'
        
#         data = {'status': 'available'}
        
#         response = self.client.post(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
        
#         # Verify change
#         self.rider.refresh_from_db()
#         self.assertEqual(self.rider.availability_status, 'available')
    
#     def test_update_availability_inactive_rider(self):
#         """Test that inactive riders cannot update availability"""
#         # Set rider to inactive
#         self.rider.operational_status = Rider.OperationalStatus.PENDING_DOCUMENTS
#         self.rider.save()
        
#         self.client.force_authenticate(user=self.user)
#         url = '/api/accounts/riders/availability/'
        
#         data = {'status': 'available'}
        
#         response = self.client.post(url, data, format='json')
        
#         self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
