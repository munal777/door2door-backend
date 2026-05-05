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
    def assign_order(*, order: Order, rider: Rider, assigned_by, notes: str = '') -> RiderOrderAssignment:
        """
        Generic assign method that handles both pickup and delivery based on order status.
        """
        if not rider.can_accept_orders:
            raise RiderAssignmentError(f'Rider {rider.user.full_name} is not available.')

        if rider.company_id != order.courier_provider_id:
            raise RiderAssignmentError(f'Order {order.order_number} does not belong to this courier.')

        # Determine assignment type and target status
        is_pickup = order.status in [Order.OrderStatus.CONFIRMED, Order.OrderStatus.PICKUP_ASSIGNED]
        is_delivery = order.status in [Order.OrderStatus.AT_DESTINATION_HUB, Order.OrderStatus.OUT_FOR_DELIVERY]

        if not (is_pickup or is_delivery):
            raise RiderAssignmentError(f'Order {order.order_number} is not in an assignable status.')

        target_status = Order.OrderStatus.PICKUP_ASSIGNED if is_pickup else Order.OrderStatus.OUT_FOR_DELIVERY
        location_city = order.sender_city if is_pickup else order.receiver_city
        remarks = (
            f"Pickup assigned to rider {rider.user.full_name}." if is_pickup 
            else f"Out for delivery with rider {rider.user.full_name}."
        )

        now = timezone.now()

        # Deactivate previous assignments
        RiderOrderAssignment.objects.select_for_update().filter(
            order=order,
            is_active=True,
        ).update(
            is_active=False,
            unassigned_at=now,
        )

        # Create new assignment
        assignment = RiderOrderAssignment.objects.create(
            order=order,
            rider=rider,
            assigned_by=assigned_by,
            notes=notes,
            is_active=True,
        )

        # Update order status
        if order.status != target_status:
            order.status = target_status
            order.save(update_fields=['status'])

        # Set rider to busy
        if rider.availability_status != Rider.AvailabilityStatus.BUSY:
            rider.availability_status = Rider.AvailabilityStatus.BUSY
            rider.save(update_fields=['availability_status', 'updated_at'])

        # Create tracking entry
        OrderTracking.objects.create(
            order=order,
            status=target_status,
            location_city=location_city,
            remarks=remarks,
        )

        return assignment

    @classmethod
    @transaction.atomic
    def bulk_assign_orders(cls, *, order_numbers: list[str], rider: Rider, assigned_by, notes: str = '') -> list[RiderOrderAssignment]:
        orders = Order.objects.filter(order_number__in=order_numbers, courier_provider=rider.company)
        if orders.count() != len(order_numbers):
            found_numbers = orders.values_list('order_number', flat=True)
            missing = set(order_numbers) - set(found_numbers)
            raise RiderAssignmentError(f"Orders not found: {', '.join(missing)}")

        assignments = []
        for order in orders:
            assignments.append(
                cls.assign_order(order=order, rider=rider, assigned_by=assigned_by, notes=notes)
            )
        return assignments

