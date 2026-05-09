from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from accounts.models import Rider
from orders.models import Order
from riders.models import RiderLocationUpdate, RiderOrderAssignment


TRACKING_ACTIVE_STATUSES = {
    Order.OrderStatus.HEADING_TO_PICKUP,
    Order.OrderStatus.OUT_FOR_DELIVERY,
}


class RiderOrderLocationConsumer(AsyncJsonWebsocketConsumer):
    """
    Real-time websocket stream for order location updates.
    """

    async def connect(self):
        self.order_number = self.scope['url_route']['kwargs']['order_number']
        self.group_name = f'order_location_{self.order_number}'

        user = self.scope.get('user')
        if not user or not getattr(user, 'is_authenticated', False):
            await self.close(code=4401)
            return

        is_allowed = await self._can_join_order_stream(user, self.order_number)
        if not is_allowed:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({
            'type': 'stream.connected',
            'order_number': self.order_number,
            'server_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        })

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get('action')
        if action != 'location.update':
            await self.send_json({'type': 'error', 'message': 'Unsupported action.'})
            return

        user = self.scope.get('user')
        can_publish = await self._can_publish_location(user, self.order_number)
        if not can_publish:
            await self.send_json({'type': 'error', 'message': 'Only assigned rider can publish location.'})
            return

        latitude = content.get('latitude')
        longitude = content.get('longitude')

        if latitude is None or longitude is None:
            await self.send_json({'type': 'error', 'message': 'latitude and longitude are required.'})
            return

        location_data = await self._store_location_update(
            user=user,
            order_number=self.order_number,
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=content.get('accuracy_meters'),
            speed_kmh=content.get('speed_kmh'),
            heading_degrees=content.get('heading_degrees'),
        )

        if not location_data:
            await self.send_json({'type': 'error', 'message': 'Failed to persist location update.'})
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'location.broadcast',
                'payload': location_data,
            },
        )

    async def location_broadcast(self, event):
        await self.send_json(
            {
                'type': 'location.update',
                **event['payload'],
            }
        )

    @database_sync_to_async
    def _can_join_order_stream(self, user, order_number):
        if not user or not user.is_authenticated:
            return False

        try:
            order = Order.objects.select_related('courier_provider', 'consumer').get(order_number=order_number)
        except Order.DoesNotExist:
            return False

        if user.user_type == 'rider' and hasattr(user, 'rider_profile'):
            return RiderOrderAssignment.objects.filter(
                order=order,
                rider=user.rider_profile,
                is_active=True,
            ).exists()

        if user.user_type == 'courier_staff' and hasattr(user, 'courier_staff_profile'):
            return user.courier_staff_profile.company_id == order.courier_provider_id

        if user.user_type == 'consumer':
            return order.consumer_id == user.id

        return False

    @database_sync_to_async
    def _can_publish_location(self, user, order_number):
        if not user or not user.is_authenticated or user.user_type != 'rider' or not hasattr(user, 'rider_profile'):
            return False

        return RiderOrderAssignment.objects.filter(
            order__order_number=order_number,
            rider=user.rider_profile,
            is_active=True,
            order__status__in=TRACKING_ACTIVE_STATUSES,
        ).exists()

    @database_sync_to_async
    def _store_location_update(self, user, order_number, latitude, longitude, accuracy_meters=None, speed_kmh=None, heading_degrees=None):
        try:
            rider = Rider.objects.get(user=user)
            assignment = RiderOrderAssignment.objects.select_related('order').get(
                order__order_number=order_number,
                rider=rider,
                is_active=True,
            )
        except (Rider.DoesNotExist, RiderOrderAssignment.DoesNotExist):
            return None

        if assignment.order.status not in TRACKING_ACTIVE_STATUSES:
            return None

        rider.update_location(latitude, longitude)

        location_update = RiderLocationUpdate.objects.create(
            assignment=assignment,
            order=assignment.order,
            rider=rider,
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy_meters,
            speed_kmh=speed_kmh,
            heading_degrees=heading_degrees,
        )

        return {
            'order_number': assignment.order.order_number,
            'rider_id': rider.id,
            'rider_name': rider.full_name,
            'latitude': str(location_update.latitude),
            'longitude': str(location_update.longitude),
            'accuracy_meters': str(location_update.accuracy_meters) if location_update.accuracy_meters is not None else None,
            'speed_kmh': str(location_update.speed_kmh) if location_update.speed_kmh is not None else None,
            'heading_degrees': str(location_update.heading_degrees) if location_update.heading_degrees is not None else None,
            'recorded_at': location_update.recorded_at.strftime('%Y-%m-%d %H:%M:%S'),
        }
