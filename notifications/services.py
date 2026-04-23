from typing import Dict, List

import logging

import requests
from django.utils import timezone

from notifications.models import UserPushToken, Notification


logger = logging.getLogger(__name__)


class PushNotificationService:
    EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'

    @classmethod
    def send_notification(cls, user_id: int, title: str, body: str, data: dict = None):
        """
        Creates an in-app Notification record and attempts to send a mobile push via Expo.
        """
        if data is None:
            data = {}

        # 1. Save to in-app inbox
        Notification.objects.create(
            user_id=user_id,
            title=title,
            body=body,
            data=data,
        )

        # 2. Get active push tokens
        tokens = list(
            UserPushToken.objects.filter(user_id=user_id, is_active=True).values('id', 'token')
        )

        if not tokens:
            return

        # 3. Prepare Expo messages
        messages = [
            {
                'to': token_row['token'],
                'sound': 'default',
                'title': title,
                'body': body,
                'data': data,
            }
            for token_row in tokens
        ]

        # 4. Dispatch to Expo
        cls._dispatch_to_expo(user_id, messages, tokens)

    @classmethod
    def send_order_accepted_notification(cls, user_id: int, order_number: str):
        cls.send_notification(
            user_id=user_id,
            title='Order Accepted',
            body=f'Your order {order_number} has been accepted.',
            data={
                'screen': 'track',
                'orderNumber': order_number,
                'event': 'order_accepted',
            }
        )

    @classmethod
    def _dispatch_to_expo(cls, user_id: int, messages: List[Dict], tokens: List[Dict]):
        try:
            response = requests.post(
                cls.EXPO_PUSH_URL,
                json=messages,
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                },
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.exception(
                'Expo push send failed for user_id=%s',
                user_id,
                exc_info=exc,
            )
            return

        if isinstance(payload, dict) and payload.get('errors'):
            logger.warning(
                'Expo push send returned top-level errors for user_id=%s: %s',
                user_id,
                payload.get('errors'),
            )

        cls._process_expo_send_results(tokens=tokens, expo_payload=payload)

    @classmethod
    def _process_expo_send_results(cls, tokens: List[Dict], expo_payload: Dict):
        results = expo_payload.get('data')
        if isinstance(results, dict):
            results = [results]

        if not isinstance(results, list):
            return

        invalid_token_ids: List[int] = []
        for index, result in enumerate(results):
            if index >= len(tokens):
                break

            if not isinstance(result, dict):
                continue

            if result.get('status') == 'ok':
                continue

            details = result.get('details') or {}
            error_code = details.get('error')

            logger.warning(
                'Expo push delivery error for token_id=%s: status=%s details=%s',
                tokens[index].get('id'),
                result.get('status'),
                details,
            )

            if error_code in {'DeviceNotRegistered', 'InvalidExpoPushToken'}:
                invalid_token_ids.append(tokens[index]['id'])

        if invalid_token_ids:
            UserPushToken.objects.filter(id__in=invalid_token_ids).update(
                is_active=False,
                updated_at=timezone.now(),
            )
