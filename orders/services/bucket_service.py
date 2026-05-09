from django.db import transaction
from django.utils import timezone
from typing import Dict, List
from ..models import (
    TransportBucket, 
    BucketTracking, 
    Order, 
    OrderTracking,
    BucketStop
)

from myproject.utils import format_datetime

class BucketTrackingService:
    """
    Service for recording bucket location tracking events and bulk updating orders
    """
    
    @staticmethod
    @transaction.atomic
    def record_tracking_event(
        bucket: TransportBucket,
        action: str,
        location_city: str,
        updated_by,
        bucket_stop=None
    ) -> Dict:
        """
        Record bucket location tracking event and bulk update all orders inside.
        """
        # Check if the exact same tracking event already exists (same action + location)
        latest_tracking = bucket.tracking_history.filter(
            action=action,
            location_city__iexact=location_city
        ).first()
        
        if latest_tracking:
            return {
                'duplicate': True,
                'message': 'Duplicate scan detected - same action already recorded at this location'
            }
        
        # Fetch all bucket orders once with related order data to avoid N+1 queries
        bucket_orders = bucket.bucket_orders.select_related('order').all()
        
        # Process orders based on scan action
        tracking_records = []
        updated_order_ids = []
        
        if action == BucketTracking.ScanAction.DEPARTED_ORIGIN:
            # Bucket departing from origin hub - all orders go IN_TRANSIT
            for bucket_order in bucket_orders:
                order = bucket_order.order
                
                # Skip orders already out for delivery or delivered
                if order.status in [
                    Order.OrderStatus.DELIVERY_ASSIGNED,
                    Order.OrderStatus.OUT_FOR_DELIVERY,
                    Order.OrderStatus.DELIVERED,
                ]:
                    continue
                
                order.status = Order.OrderStatus.IN_TRANSIT
                order.save(update_fields=['status'])
                updated_order_ids.append(order.id)
                
                tracking_records.append(
                    OrderTracking(
                        order=order,
                        status=Order.OrderStatus.IN_TRANSIT,
                        location_city=location_city,
                        remarks=f"Your package has departed from {location_city} and is on its way to {order.receiver_city}. It will be delivered soon."
                    )
                )
            
        elif action == BucketTracking.ScanAction.ARRIVED_TRANSIT:
            # Bucket arrived at a transit hub - orders remain IN_TRANSIT (passing through)
            for bucket_order in bucket_orders:
                order = bucket_order.order
                
                # Skip orders already at destination or beyond
                if order.status in [
                    Order.OrderStatus.AT_DESTINATION_HUB,
                    Order.OrderStatus.DELIVERY_ASSIGNED,
                    Order.OrderStatus.OUT_FOR_DELIVERY,
                    Order.OrderStatus.DELIVERED,
                ]:
                    continue
                
                order.status = Order.OrderStatus.IN_TRANSIT
                order.save(update_fields=['status'])
                updated_order_ids.append(order.id)
                
                tracking_records.append(
                    OrderTracking(
                        order=order,
                        status=Order.OrderStatus.IN_TRANSIT,
                        location_city=location_city,
                        remarks=f"Your package has arrived at {location_city} transit facility and is being processed for onward delivery to {order.receiver_city}."
                    )
                )
        
        elif action == BucketTracking.ScanAction.DEPARTED_TRANSIT:
            # Bucket departing from transit hub - orders continue IN_TRANSIT
            for bucket_order in bucket_orders:
                order = bucket_order.order
                
                # Skip orders already at destination or beyond
                if order.status in [
                    Order.OrderStatus.AT_DESTINATION_HUB,
                    Order.OrderStatus.DELIVERY_ASSIGNED,
                    Order.OrderStatus.OUT_FOR_DELIVERY,
                    Order.OrderStatus.DELIVERED,
                ]:
                    continue
                
                order.status = Order.OrderStatus.IN_TRANSIT
                order.save(update_fields=['status'])
                updated_order_ids.append(order.id)
                
                tracking_records.append(
                    OrderTracking(
                        order=order,
                        status=Order.OrderStatus.IN_TRANSIT,
                        location_city=location_city,
                        remarks=f"Your package has left {location_city} transit hub and is moving closer to your delivery location in {order.receiver_city}."
                    )
                )
            
        elif action == BucketTracking.ScanAction.ARRIVED_DESTINATION:
            # Bucket arrived at destination hub - check each order's destination
            for bucket_order in bucket_orders:
                order = bucket_order.order
                
                # Skip orders already at destination (unloaded at previous stop), out for delivery, or delivered
                if order.status in [
                    Order.OrderStatus.AT_DESTINATION_HUB,
                    Order.OrderStatus.DELIVERY_ASSIGNED,
                    Order.OrderStatus.OUT_FOR_DELIVERY,
                    Order.OrderStatus.DELIVERED,
                ]:
                    continue
                
                # Check if this location is the order's destination
                if order.receiver_city.lower() == location_city.lower():
                    # Order has reached its destination hub
                    new_status = Order.OrderStatus.AT_DESTINATION_HUB
                    remarks = f"Great news! Your package has arrived at {location_city} delivery hub. It will be out for delivery soon."
                else:
                    # Order at wrong destination (routing error or multi-leg)
                    # Keep it IN_TRANSIT
                    new_status = Order.OrderStatus.IN_TRANSIT
                    remarks = f"Your package is currently at {location_city} hub and will continue its journey to {order.receiver_city}."
                
                order.status = new_status
                order.save(update_fields=['status'])
                updated_order_ids.append(order.id)
                
                tracking_records.append(
                    OrderTracking(
                        order=order,
                        status=new_status,
                        location_city=location_city,
                        remarks=remarks
                    )
                )
                    
        elif action == BucketTracking.ScanAction.PARTIAL_UNLOAD:
            # Partial unload at a specific stop - only update unloaded orders
            if bucket_stop:
                orders_for_stop = bucket_stop.orders_for_this_stop.select_related('order').all()
                
                for bucket_order in orders_for_stop:
                    order = bucket_order.order
                    
                    # Skip orders already delivered
                    if order.status == Order.OrderStatus.DELIVERED:
                        continue
                    
                    # Orders being unloaded have reached their destination
                    new_status = Order.OrderStatus.AT_DESTINATION_HUB
                    remarks = f"Your package has been successfully received at {location_city} delivery center and is ready for final delivery."
                    
                    order.status = new_status
                    order.save(update_fields=['status'])
                    updated_order_ids.append(order.id)
                    
                    tracking_records.append(
                        OrderTracking(
                            order=order,
                            status=new_status,
                            location_city=location_city,
                            remarks=remarks
                        )
                    )

        if not tracking_records:
            return {
                'skipped': True,
                'message': 'No orders to update - all orders already in correct status'
            }
        
        # Create bucket tracking record
        bucket_tracking = BucketTracking.objects.create(
            bucket=bucket,
            action=action,
            location_city=location_city,
            bucket_stop=bucket_stop,
            scanned_by=updated_by,
            notes="",
            orders_updated_count=len(tracking_records)
        )
        
        # Bulk create all order tracking records
        OrderTracking.objects.bulk_create(tracking_records)
        
        return {
            'bucket_tracking_id': bucket_tracking.id,
            'action': action,
            'location_city': location_city,
            'orders_updated': len(tracking_records),
            'order_ids': updated_order_ids,
            'duplicate': False,
            'timestamp': format_datetime(bucket_tracking.created_at)
        }
    
    @staticmethod
    def get_bucket_current_location(bucket: TransportBucket) -> Dict:
        """
        Get the last known location of a bucket based on tracking history
        """
        latest_tracking = bucket.tracking_history.first()  # ordered by -created_at
        
        if not latest_tracking:
            return {
                'location_city': bucket.origin_city,
                'action': 'created',
                'timestamp': bucket.created_at
            }
        
        return {
            'location_city': latest_tracking.location_city,
            'action': latest_tracking.action,
            'timestamp': latest_tracking.created_at
        }