from django.urls import path
from .views import (
    AnalyticsOverviewAPIView,
    OrdersAnalyticsAPIView,
    RevenueAnalyticsAPIView,
    ShipmentsAnalyticsAPIView,
)

urlpatterns = [
    path("analytics/overview/", AnalyticsOverviewAPIView.as_view(), name="analytics-overview"),
    path("analytics/orders/", OrdersAnalyticsAPIView.as_view(), name="analytics-orders"),
    path("analytics/revenue/", RevenueAnalyticsAPIView.as_view(), name="analytics-revenue"),
    path("analytics/shipments/", ShipmentsAnalyticsAPIView.as_view(), name="analytics-shipments"),
]