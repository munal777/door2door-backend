from django.test import TestCase
from django.contrib.auth import get_user_model

from unittest.mock import Mock, patch

from notifications.models import UserPushToken
from notifications.serializers import TokenRegisterSerializer
from notifications.services import PushNotificationService


User = get_user_model()


class TokenRegisterSerializerTests(TestCase):
	def test_validate_token_strips_whitespace(self):
		serializer = TokenRegisterSerializer(data={'token': '  ExponentPushToken[abc123]  ', 'platform': 'android'})

		self.assertTrue(serializer.is_valid())
		self.assertEqual(serializer.validated_data['token'], 'ExponentPushToken[abc123]')

	def test_validate_token_rejects_blank_after_strip(self):
		serializer = TokenRegisterSerializer(data={'token': '   ', 'platform': 'android'})

		self.assertFalse(serializer.is_valid())
		self.assertIn('token', serializer.errors)


class PushNotificationServiceTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email='push-user@example.com',
			password='password123',
		)

	def test_send_order_accepted_notification_no_tokens_skips_network_call(self):
		with patch('notifications.services.requests.post') as mock_post:
			PushNotificationService.send_order_accepted_notification(
				user_id=self.user.id,
				order_number='ORD-001',
			)

		mock_post.assert_not_called()

	def test_send_order_accepted_notification_deactivates_invalid_token(self):
		token_row = UserPushToken.objects.create(
			user=self.user,
			token='ExponentPushToken[invalid-token]',
			platform=UserPushToken.Platform.ANDROID,
		)

		mock_response = Mock()
		mock_response.raise_for_status.return_value = None
		mock_response.json.return_value = {
			'data': [
				{
					'status': 'error',
					'message': 'The recipient device is not registered',
					'details': {'error': 'DeviceNotRegistered'},
				}
			]
		}

		with patch('notifications.services.requests.post', return_value=mock_response) as mock_post:
			PushNotificationService.send_order_accepted_notification(
				user_id=self.user.id,
				order_number='ORD-002',
			)

		mock_post.assert_called_once()
		token_row.refresh_from_db()
		self.assertFalse(token_row.is_active)
