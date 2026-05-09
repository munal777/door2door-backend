from celery import shared_task

from notifications.services import PushNotificationService


@shared_task(bind=True, max_retries=0)
def send_order_accepted_notification(self, user_id: int, order_number: str):
    """
    Async task to send the order-accepted push notification.
    """
    return PushNotificationService.send_order_accepted_notification(
        user_id=user_id,
        order_number=order_number,
    )


@shared_task(bind=True, max_retries=0)
def send_heading_to_pickup_notification(self, user_id: int, order_number: str):
    """
    Async task to send the heading-to-pickup push notification.
    """
    return PushNotificationService.send_heading_to_pickup_notification(
        user_id=user_id,
        order_number=order_number,
    )