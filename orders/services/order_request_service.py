from django.db.models import Value
from django.db.models.functions import Coalesce, Lower, Trim
from django.utils import timezone

from ..models import OrderRequest, OrderRequestCourierResponse


class OrderRequestVisibilityService:
    """
    Centralized visibility rules for courier-side order request feeds.
    """

    @staticmethod
    def _normalize_location(value):
        if not value:
            return ''
        return value.strip().lower()

    @classmethod
    def _normalized_courier_location(cls, courier_provider):
        if not courier_provider:
            return '', ''
        return (
            cls._normalize_location(getattr(courier_provider, 'city', '')),
            cls._normalize_location(getattr(courier_provider, 'state', '')),
        )

    @staticmethod
    def _queryset_with_normalized_pickup():
        return OrderRequest.objects.annotate(
            pickup_city_normalized=Lower(Trim(Coalesce('pickup_city', Value('')))),
            pickup_state_normalized=Lower(Trim(Coalesce('pickup_state', Value('')))),
        )

    @staticmethod
    def expire_stale_pending_requests(now=None):
        current_time = now or timezone.now()
        OrderRequest.objects.filter(
            status=OrderRequest.RequestStatus.PENDING,
            expires_at__lte=current_time,
        ).update(status=OrderRequest.RequestStatus.EXPIRED)
        return current_time

    @classmethod
    def nearby_pending_requests_for_courier(cls, courier_provider):
        if not courier_provider:
            return OrderRequest.objects.none()

        courier_city, courier_state = cls._normalized_courier_location(courier_provider)

        # City is the primary scope boundary for nearby visibility.
        # State differences like "Bagmati" vs "Bagmati Province" should not hide
        # requests for the same city.
        if not courier_city:
            return OrderRequest.objects.none()

        now = cls.expire_stale_pending_requests()

        responded_request_ids = OrderRequestCourierResponse.objects.filter(
            courier_provider=courier_provider,
        ).values_list('order_request_id', flat=True)

        return (
            cls._queryset_with_normalized_pickup()
            .filter(
                status=OrderRequest.RequestStatus.PENDING,
                expires_at__gt=now,
                pickup_city_normalized=courier_city,
            )
            .exclude(id__in=responded_request_ids)
            .order_by('-created_at')
        )

    @classmethod
    def is_request_in_courier_nearby_scope(cls, order_request, courier_provider):
        """
        Check if request is pending, not expired, and in courier city/state.
        Does not exclude prior courier responses.
        """
        if not courier_provider or not order_request:
            return False

        courier_city, courier_state = cls._normalized_courier_location(courier_provider)
        if not courier_city:
            return False

        now = cls.expire_stale_pending_requests()

        return cls._queryset_with_normalized_pickup().filter(
            id=order_request.id,
            status=OrderRequest.RequestStatus.PENDING,
            expires_at__gt=now,
            pickup_city_normalized=courier_city,
        ).exists()