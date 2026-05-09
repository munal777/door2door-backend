from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from orders.models import Order
from riders.models import RiderOrderAssignment

@receiver(post_save, sender=Order)
def auto_deactivate_rider_assignment(sender, instance, **kwargs):
    """
    Automatically deactivate rider assignments when an order moves out of 
    active assignment phases (pickup/delivery).
    """

    ACTIVE_PHASES = [
        Order.OrderStatus.PICKUP_ASSIGNED,
        Order.OrderStatus.HEADING_TO_PICKUP,
        Order.OrderStatus.PICKED_UP,
        Order.OrderStatus.OUT_FOR_DELIVERY,
        Order.OrderStatus.DELIVERY_ASSIGNED,
    ]

    # If the order is NOT in an active phase, any currently active assignment
    # for this order should be deactivated.
    if instance.status not in ACTIVE_PHASES:
        # Find the active assignment and deactivate it
        active_assignment = RiderOrderAssignment.objects.filter(
            order=instance,
            is_active=True
        ).first()

        if active_assignment:
            active_assignment.is_active = False
            active_assignment.unassigned_at = timezone.now()
            active_assignment.save(update_fields=['is_active', 'unassigned_at'])
            
            # Also reset rider availability if they have no other active assignments
            # (Assuming one assignment at a time for now, but we can be more robust)
            rider = active_assignment.rider
            has_other_active = RiderOrderAssignment.objects.filter(
                rider=rider,
                is_active=True
            ).exists()
            
            if not has_other_active:
                rider.availability_status = 'available'
                rider.save(update_fields=['availability_status'])
