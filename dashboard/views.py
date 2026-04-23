from datetime import timedelta
from decimal import Decimal

from django.db.models import (
    Avg,
    Count,
    DecimalField,
    DurationField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import permissions, status
from rest_framework.views import APIView

from myproject.permissions import IsCourierStaff
from myproject.utils import api_response
from orders.models import BucketOrder, Order, TransportBucket


class AnalyticsBaseAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCourierStaff]

    PRESET_RANGES = {
        "week": 7,
        "month": 30,
        "quarter": 90,
    }
    GROUP_BY_OPTIONS = {"auto", "day", "week", "month"}

    def _money_field(self):
        return DecimalField(max_digits=14, decimal_places=2)

    def _zero_money(self):
        return Value(Decimal("0.00"), output_field=self._money_field())

    def _sum_money(self, field_name, q_filter=None):
        kwargs = {"output_field": self._money_field()}
        if q_filter is not None:
            kwargs["filter"] = q_filter

        return Coalesce(
            Sum(field_name, **kwargs),
            self._zero_money(),
            output_field=self._money_field(),
        )

    def _avg_money(self, field_name):
        return Coalesce(
            Avg(field_name, output_field=self._money_field()),
            self._zero_money(),
            output_field=self._money_field(),
        )

    def _resolve_date_window(self, request):
        start_date_raw = request.query_params.get("start_date")
        end_date_raw = request.query_params.get("end_date")
        range_preset = request.query_params.get("range", "month")
        today = timezone.localdate()

        if start_date_raw or end_date_raw:
            if not start_date_raw or not end_date_raw:
                return None, None, None, api_response(
                    is_success=False,
                    error_message="Both start_date and end_date are required for custom range.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            start_date = parse_date(start_date_raw)
            end_date = parse_date(end_date_raw)
            if not start_date or not end_date:
                return None, None, None, api_response(
                    is_success=False,
                    error_message="Invalid date format. Use YYYY-MM-DD.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            if start_date > end_date:
                return None, None, None, api_response(
                    is_success=False,
                    error_message="start_date cannot be greater than end_date.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            return start_date, end_date, "custom", None

        if range_preset not in self.PRESET_RANGES:
            return None, None, None, api_response(
                is_success=False,
                error_message="Invalid range. Supported values: week, month, quarter.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        days = self.PRESET_RANGES[range_preset]
        start_date = today - timedelta(days=days - 1)
        return start_date, today, range_preset, None

    def _resolve_group_by(self, request, start_date, end_date):
        requested = request.query_params.get("group_by", "auto")
        if requested not in self.GROUP_BY_OPTIONS:
            return None, api_response(
                is_success=False,
                error_message="Invalid group_by. Supported values: auto, day, week, month.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if requested != "auto":
            return requested, None

        total_days = (end_date - start_date).days + 1
        if total_days <= 45:
            return "day", None
        if total_days <= 180:
            return "week", None
        return "month", None

    def _period_trunc(self, field_name, group_by):
        if group_by == "day":
            return TruncDate(field_name)
        if group_by == "week":
            return TruncWeek(field_name)
        return TruncMonth(field_name)

    def _format_period(self, value, group_by):
        if not value:
            return ""
        if group_by == "month":
            return value.strftime("%Y-%m")
        return value.strftime("%Y-%m-%d")

    def _build_meta(self, start_date, end_date, range_mode, group_by):
        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "range": range_mode,
            "group_by": group_by,
            "total_days": (end_date - start_date).days + 1,
        }

    def _orders_in_window(self, courier_provider, start_date, end_date):
        return Order.objects.filter(
            courier_provider=courier_provider,
            created_at__date__range=(start_date, end_date),
        )


class AnalyticsOverviewAPIView(AnalyticsBaseAPIView):
    """High-level KPIs for analytics landing and header cards."""

    def get(self, request):
        start_date, end_date, range_mode, error_response = self._resolve_date_window(
            request
        )
        if error_response:
            return error_response

        group_by, group_error = self._resolve_group_by(request, start_date, end_date)
        if group_error:
            return group_error

        courier_provider = request.courier
        orders = self._orders_in_window(courier_provider, start_date, end_date)
        created_buckets = TransportBucket.objects.filter(
            courier_provider=courier_provider,
            created_at__date__range=(start_date, end_date),
        )

        order_agg = orders.aggregate(
            total_orders=Count("id"),
            delivered_orders=Count("id", filter=Q(status=Order.OrderStatus.DELIVERED)),
            cancelled_orders=Count("id", filter=Q(status=Order.OrderStatus.CANCELLED)),
            total_revenue=self._sum_money("total_price"),
            avg_order_value=self._avg_money("total_price"),
        )
        total_orders = order_agg["total_orders"]
        delivered_orders = order_agg["delivered_orders"]

        result = {
            "meta": self._build_meta(start_date, end_date, range_mode, group_by),
            "summary": {
                "total_orders": total_orders,
                "delivered_orders": delivered_orders,
                "delivery_rate": round((delivered_orders / total_orders) * 100, 2)
                if total_orders
                else 0,
                "cancelled_orders": order_agg["cancelled_orders"],
                "total_revenue": float(order_agg["total_revenue"]),
                "average_order_value": round(float(order_agg["avg_order_value"]), 2),
                "active_buckets": TransportBucket.objects.filter(
                    courier_provider=courier_provider,
                    closed_at__isnull=True,
                ).count(),
                "created_buckets": created_buckets.count(),
            },
        }

        return api_response(
            result=result,
            is_success=True,
            status_code=status.HTTP_200_OK,
        )


class OrdersAnalyticsAPIView(AnalyticsBaseAPIView):
    """Order analytics with dynamic windowing and chart-ready trend output."""

    def get(self, request):
        start_date, end_date, range_mode, error_response = self._resolve_date_window(
            request
        )
        if error_response:
            return error_response

        group_by, group_error = self._resolve_group_by(request, start_date, end_date)
        if group_error:
            return group_error

        orders = self._orders_in_window(request.courier, start_date, end_date)

        summary = orders.aggregate(
            total_orders=Count("id"),
            delivered_orders=Count("id", filter=Q(status=Order.OrderStatus.DELIVERED)),
            cancelled_orders=Count("id", filter=Q(status=Order.OrderStatus.CANCELLED)),
            returned_orders=Count("id", filter=Q(status=Order.OrderStatus.RETURNED)),
            total_revenue=self._sum_money("total_price"),
            avg_order_value=self._avg_money("total_price"),
        )

        total_orders = summary["total_orders"]
        completed_orders = (
            summary["delivered_orders"]
            + summary["cancelled_orders"]
            + summary["returned_orders"]
        )
        active_orders = max(total_orders - completed_orders, 0)

        status_breakdown = list(
            orders.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        service_breakdown = list(
            orders.values("service_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        payment_breakdown = list(
            orders.values("payment_method")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        trend_qs = (
            orders.annotate(period=self._period_trunc("created_at", group_by))
            .values("period")
            .annotate(
                orders=Count("id"),
                delivered=Count("id", filter=Q(status=Order.OrderStatus.DELIVERED)),
                cancelled=Count("id", filter=Q(status=Order.OrderStatus.CANCELLED)),
                revenue=self._sum_money("total_price"),
            )
            .order_by("period")
        )

        trend = [
            {
                "period_start": self._format_period(item["period"], group_by),
                "orders": item["orders"],
                "delivered": item["delivered"],
                "cancelled": item["cancelled"],
                "revenue": float(item["revenue"]),
            }
            for item in trend_qs
        ]

        result = {
            "meta": self._build_meta(start_date, end_date, range_mode, group_by),
            "summary": {
                "total_orders": total_orders,
                "active_orders": active_orders,
                "delivered_orders": summary["delivered_orders"],
                "cancelled_orders": summary["cancelled_orders"],
                "returned_orders": summary["returned_orders"],
                "fulfillment_rate": round((summary["delivered_orders"] / total_orders) * 100, 2)
                if total_orders
                else 0,
                "total_revenue": float(summary["total_revenue"]),
                "average_order_value": round(float(summary["avg_order_value"]), 2),
            },
            "status_breakdown": status_breakdown,
            "service_breakdown": service_breakdown,
            "payment_breakdown": payment_breakdown,
            "trend": trend,
        }

        return api_response(
            result=result,
            is_success=True,
            status_code=status.HTTP_200_OK,
        )


class RevenueAnalyticsAPIView(AnalyticsBaseAPIView):
    """Revenue analytics with dynamic date filtering and grouped trend data."""

    def get(self, request):
        start_date, end_date, range_mode, error_response = self._resolve_date_window(
            request
        )
        if error_response:
            return error_response

        group_by, group_error = self._resolve_group_by(request, start_date, end_date)
        if group_error:
            return group_error

        orders = self._orders_in_window(request.courier, start_date, end_date)

        summary = orders.aggregate(
            total_revenue=self._sum_money("total_price"),
            paid_revenue=self._sum_money(
                "total_price",
                q_filter=Q(payment_status=Order.PaymentStatus.PAID),
            ),
            pending_revenue=self._sum_money(
                "total_price",
                q_filter=Q(payment_status=Order.PaymentStatus.PENDING),
            ),
            order_count=Count("id"),
            average_order_value=self._avg_money("total_price"),
        )

        trend_qs = (
            orders.annotate(period=self._period_trunc("created_at", group_by))
            .values("period")
            .annotate(
                revenue=self._sum_money("total_price"),
                paid_revenue=self._sum_money(
                    "total_price",
                    q_filter=Q(payment_status=Order.PaymentStatus.PAID),
                ),
                order_count=Count("id"),
            )
            .order_by("period")
        )

        breakdown_service = list(
            orders.values("service_type")
            .annotate(revenue=self._sum_money("total_price"), orders=Count("id"))
            .order_by("-revenue")
        )
        breakdown_payment = list(
            orders.values("payment_method")
            .annotate(revenue=self._sum_money("total_price"), orders=Count("id"))
            .order_by("-revenue")
        )
        breakdown_order_type = list(
            orders.values("order_type")
            .annotate(revenue=self._sum_money("total_price"), orders=Count("id"))
            .order_by("-revenue")
        )

        top_sender_cities = list(
            orders.values("sender_city")
            .annotate(revenue=self._sum_money("total_price"), orders=Count("id"))
            .order_by("-revenue")[:10]
        )
        top_receiver_cities = list(
            orders.values("receiver_city")
            .annotate(revenue=self._sum_money("total_price"), orders=Count("id"))
            .order_by("-revenue")[:10]
        )

        result = {
            "meta": self._build_meta(start_date, end_date, range_mode, group_by),
            "summary": {
                "total_revenue": float(summary["total_revenue"]),
                "paid_revenue": float(summary["paid_revenue"]),
                "pending_revenue": float(summary["pending_revenue"]),
                "order_count": summary["order_count"],
                "average_order_value": round(float(summary["average_order_value"]), 2),
            },
            "trend": [
                {
                    "period_start": self._format_period(item["period"], group_by),
                    "revenue": float(item["revenue"]),
                    "paid_revenue": float(item["paid_revenue"]),
                    "order_count": item["order_count"],
                }
                for item in trend_qs
            ],
            "breakdown": {
                "service_type": [
                    {
                        "service_type": item["service_type"],
                        "revenue": float(item["revenue"]),
                        "orders": item["orders"],
                    }
                    for item in breakdown_service
                ],
                "payment_method": [
                    {
                        "payment_method": item["payment_method"],
                        "revenue": float(item["revenue"]),
                        "orders": item["orders"],
                    }
                    for item in breakdown_payment
                ],
                "order_type": [
                    {
                        "order_type": item["order_type"],
                        "revenue": float(item["revenue"]),
                        "orders": item["orders"],
                    }
                    for item in breakdown_order_type
                ],
            },
            "top_sender_cities": [
                {
                    "city": item["sender_city"],
                    "revenue": float(item["revenue"]),
                    "orders": item["orders"],
                }
                for item in top_sender_cities
            ],
            "top_receiver_cities": [
                {
                    "city": item["receiver_city"],
                    "revenue": float(item["revenue"]),
                    "orders": item["orders"],
                }
                for item in top_receiver_cities
            ],
        }

        return api_response(
            result=result,
            is_success=True,
            status_code=status.HTTP_200_OK,
        )


class ShipmentsAnalyticsAPIView(AnalyticsBaseAPIView):
    """Shipment and transport analytics scoped to the selected date window."""

    def get(self, request):
        start_date, end_date, range_mode, error_response = self._resolve_date_window(
            request
        )
        if error_response:
            return error_response

        group_by, group_error = self._resolve_group_by(request, start_date, end_date)
        if group_error:
            return group_error

        courier_provider = request.courier
        buckets = TransportBucket.objects.filter(
            courier_provider=courier_provider,
            created_at__date__range=(start_date, end_date),
        )

        buckets_summary = buckets.aggregate(
            created_buckets=Count("id"),
            avg_orders_per_bucket=Coalesce(
                Avg("bucket_orders__id", output_field=self._money_field()),
                self._zero_money(),
                output_field=self._money_field(),
            ),
        )
        closed_buckets_in_range = TransportBucket.objects.filter(
            courier_provider=courier_provider,
            closed_at__date__range=(start_date, end_date),
        )

        close_duration = closed_buckets_in_range.aggregate(
            avg_close_time=Avg(
                ExpressionWrapper(
                    F("closed_at") - F("created_at"),
                    output_field=DurationField(),
                )
            )
        )["avg_close_time"]
        avg_close_hours = (
            round(close_duration.total_seconds() / 3600, 2) if close_duration else 0
        )

        trend_qs = (
            buckets.annotate(period=self._period_trunc("created_at", group_by))
            .values("period")
            .annotate(
                created_buckets=Count("id"),
                orders_loaded=Count("bucket_orders__id"),
            )
            .order_by("period")
        )

        routes_qs = (
            self._orders_in_window(courier_provider, start_date, end_date)
            .values("sender_city", "receiver_city")
            .annotate(
                order_count=Count("id"),
                total_revenue=self._sum_money("total_price"),
            )
            .order_by("-order_count")[:10]
        )

        result = {
            "meta": self._build_meta(start_date, end_date, range_mode, group_by),
            "summary": {
                "created_buckets": buckets_summary["created_buckets"],
                "active_buckets": TransportBucket.objects.filter(
                    courier_provider=courier_provider,
                    closed_at__isnull=True,
                ).count(),
                "closed_buckets_in_range": closed_buckets_in_range.count(),
                "orders_in_active_buckets": BucketOrder.objects.filter(
                    bucket__courier_provider=courier_provider,
                    bucket__closed_at__isnull=True,
                ).count(),
                "avg_orders_per_bucket": round(
                    float(buckets_summary["avg_orders_per_bucket"]),
                    2,
                ),
                "avg_close_time_hours": avg_close_hours,
            },
            "trend": [
                {
                    "period_start": self._format_period(item["period"], group_by),
                    "created_buckets": item["created_buckets"],
                    "orders_loaded": item["orders_loaded"],
                }
                for item in trend_qs
            ],
            "top_routes": [
                {
                    "from_city": item["sender_city"],
                    "to_city": item["receiver_city"],
                    "order_count": item["order_count"],
                    "total_revenue": float(item["total_revenue"]),
                }
                for item in routes_qs
            ],
        }

        return api_response(
            result=result,
            is_success=True,
            status_code=status.HTTP_200_OK,
        )
