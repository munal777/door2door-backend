from django.urls import path
from .views import (
    # Manual Order Views
    ManualOrderCreateAPIView,
    OrderListAPIView,
    OrderDetailAPIView,
    UpdateOrderPaymentStatusAPIView,
    # Bucket Management Views
    TransportBucketCreateAPIView,
    TransportBucketListAPIView,
    TransportBucketDetailAPIView,
    AddOrdersToBucketAPIView,
    UpdateBucketLocationAPIView,
    CloseBucketAPIView,
    # Public Tracking Views
    PublicOrderTrackingAPIView,
    # Online Order Request Views (Consumer)
    OrderRequestCreateAPIView,
    ConsumerOrderRequestHistoryAPIView,
    ConsumerOrderRequestDetailAPIView,
    CancelOrderRequestAPIView,
    # Online Order Request Views (Courier Nearby)
    NearbyOrderRequestListAPIView,
    NearbyOrderRequestDetailAPIView,
    NearbyOrderRequestActionAPIView,
)

app_name = 'orders'

urlpatterns = [
     # Order Management
    path('manual/', ManualOrderCreateAPIView.as_view(), name='manual-order-create'),
    path('list/', OrderListAPIView.as_view(), name='order-list'),

    # Online Order Requests (Consumer)
    path('requests/', OrderRequestCreateAPIView.as_view(), name='order-request-create'),
    path('requests/list/', ConsumerOrderRequestHistoryAPIView.as_view(), name='order-request-list'),
    path('requests/nearby/', NearbyOrderRequestListAPIView.as_view(), name='nearby-order-request-list'),
    path('requests/nearby/<str:request_number>/', NearbyOrderRequestDetailAPIView.as_view(), name='nearby-order-request-detail'),
    path('requests/nearby/<str:request_number>/action/', NearbyOrderRequestActionAPIView.as_view(), name='nearby-order-request-action'),
    path('requests/<str:request_number>/cancel/', CancelOrderRequestAPIView.as_view(), name='order-request-cancel'),
    path('requests/<str:request_number>/', ConsumerOrderRequestDetailAPIView.as_view(), name='order-request-detail'),

    # Bucket routes — most specific FIRST
    path('buckets/list/', TransportBucketListAPIView.as_view(), name='bucket-list'),
    path('buckets/<str:bucket_number>/add-orders/', AddOrdersToBucketAPIView.as_view(), name='bucket-add-orders'),
    path('buckets/<str:bucket_number>/update-location/', UpdateBucketLocationAPIView.as_view(), name='bucket-update-location'),
    path('buckets/<str:bucket_number>/close/', CloseBucketAPIView.as_view(), name='bucket-close'),
    path('buckets/<str:bucket_number>/', TransportBucketDetailAPIView.as_view(), name='bucket-detail'),
    path('buckets/', TransportBucketCreateAPIView.as_view(), name='bucket-create'),  # ← LAST among buckets

    # Public tracking
    path('track/<str:order_number>/', PublicOrderTrackingAPIView.as_view(), name='public-order-tracking'),

    # Order wildcards — MUST BE LAST
    path('<str:order_number>/payment/', UpdateOrderPaymentStatusAPIView.as_view(), name='update-payment-status'),
    path('<str:order_number>/', OrderDetailAPIView.as_view(), name='order-detail'),
]
