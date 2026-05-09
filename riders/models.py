from django.db import models
from django.db.models import Q


class RiderOrderAssignment(models.Model):
	"""
	Tracks assignment of an order to a rider.
	Supports reassignment history while keeping only one active assignment.
	"""

	order = models.ForeignKey(
		'orders.Order',
		on_delete=models.CASCADE,
		related_name='rider_assignments',
		unique=True
	)
	rider = models.ForeignKey(
		'accounts.Rider',
		on_delete=models.CASCADE,
		related_name='order_assignments',
	)
	assigned_by = models.ForeignKey(
		'accounts.User',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='created_rider_assignments',
	)
	is_active = models.BooleanField(default=True)
	notes = models.TextField(blank=True)
	assigned_at = models.DateTimeField(auto_now_add=True)
	unassigned_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		ordering = ['-assigned_at']
		indexes = [
			models.Index(fields=['order', 'is_active']),
			models.Index(fields=['rider', 'is_active']),
		]
		constraints = [
			models.UniqueConstraint(
				fields=['order'],
				condition=Q(is_active=True),
				name='unique_active_rider_assignment_per_order',
			),
		]

	def __str__(self):
		return f"{self.order.order_number} -> {self.rider.full_name}"


class RiderLocationUpdate(models.Model):
	"""
	Stores rider live location pings for an assigned order.
	Used for real-time tracking driven by websocket location events.
	"""

	assignment = models.ForeignKey(
		RiderOrderAssignment,
		on_delete=models.CASCADE,
		related_name='location_updates',
	)
	order = models.ForeignKey(
		'orders.Order',
		on_delete=models.CASCADE,
		related_name='rider_location_updates',
	)
	rider = models.ForeignKey(
		'accounts.Rider',
		on_delete=models.CASCADE,
		related_name='location_updates',
	)
	latitude = models.DecimalField(max_digits=9, decimal_places=6)
	longitude = models.DecimalField(max_digits=9, decimal_places=6)
	accuracy_meters = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
	speed_kmh = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
	heading_degrees = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
	recorded_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-recorded_at']
		indexes = [
			models.Index(fields=['order', 'recorded_at']),
			models.Index(fields=['rider', 'recorded_at']),
			models.Index(fields=['assignment', 'recorded_at']),
		]

	def __str__(self):
		return f"{self.order.order_number} @ {self.recorded_at}"
