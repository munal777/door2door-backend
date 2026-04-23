from django.db import transaction
from django.utils import timezone

from accounts.models import Rider
from orders.models import Order, OrderTracking
from riders.models import RiderOrderAssignment


class RiderAssignmentError(Exception):
    pass


class RiderAssignmentService:
    @staticmethod
    @transaction.atomic
    def assign_online_order_for_pickup(*, order: Order, rider: Rider, assigned_by, notes: str = '') -> RiderOrderAssignment:
        if order.order_type != Order.OrderType.ONLINE:
            raise RiderAssignmentError('Only online orders can be assigned with this API.')

        if order.status not in [Order.OrderStatus.CONFIRMED, Order.OrderStatus.PICKUP_ASSIGNED]:
            raise RiderAssignmentError('Order must be in confirmed or pickup_assigned status for rider assignment.')

        if not rider.can_accept_orders:
            raise RiderAssignmentError('Selected rider is not available for assignment.')

        if rider.company_id != order.courier_provider_id:
            raise RiderAssignmentError('Selected rider does not belong to this courier provider.')

        now = timezone.now()

        RiderOrderAssignment.objects.select_for_update().filter(
            order=order,
            is_active=True,
        ).update(
            is_active=False,
            unassigned_at=now,
        )

        assignment = RiderOrderAssignment.objects.create(
            order=order,
            rider=rider,
            assigned_by=assigned_by,
            notes=notes,
            is_active=True,
        )

        if order.status != Order.OrderStatus.PICKUP_ASSIGNED:
            order.status = Order.OrderStatus.PICKUP_ASSIGNED
            order.save(update_fields=['status'])

        if rider.availability_status != Rider.AvailabilityStatus.BUSY:
            rider.availability_status = Rider.AvailabilityStatus.BUSY
            rider.save(update_fields=['availability_status', 'updated_at'])

        OrderTracking.objects.create(
            order=order,
            status=Order.OrderStatus.PICKUP_ASSIGNED,
            location_city=order.sender_city,
            remarks=f"Pickup assigned to rider {rider.user.full_name}. Rider is on standby for pickup from sender location.",
        )

        return assignment
