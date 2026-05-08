from django.urls import path

from riders.views.app import (
    RiderAppAvailabilityUpdateAPIView,
    RiderAppProfileAPIView,
    RiderAssignedOrderDetailAPIView,
    RiderAssignedOrderListAPIView,
    RiderAssignedOrderStatusUpdateAPIView,
    RiderOrderHistoryListAPIView,
    RiderOrderLiveLocationUpdateAPIView,
)
from riders.views.courier_crm import (
    ActiveRiderAssignmentListAPIView,
    AssignableOnlineOrderListAPIView,
    BulkAssignOrdersAPIView,
    CourierRiderDetailAPIView,
    CourierRiderListAPIView,
    CourierRiderStatusUpdateAPIView,
)

urlpatterns = [
    path('app/profile/', RiderAppProfileAPIView.as_view(), name='rider-app-profile'),
    path('app/availability/', RiderAppAvailabilityUpdateAPIView.as_view(), name='rider-app-availability'),
    path('app/orders/', RiderAssignedOrderListAPIView.as_view(), name='rider-assigned-order-list'),
    # 'history' must come before <str:order_number> to avoid being captured as an order number
    path('app/orders/history/', RiderOrderHistoryListAPIView.as_view(), name='rider-order-history'),
    path('app/orders/<str:order_number>/', RiderAssignedOrderDetailAPIView.as_view(), name='rider-assigned-order-detail'),
    path('app/orders/<str:order_number>/status/', RiderAssignedOrderStatusUpdateAPIView.as_view(), name='rider-assigned-order-status-update'),
    path('app/orders/<str:order_number>/location/', RiderOrderLiveLocationUpdateAPIView.as_view(), name='rider-order-live-location-update'),

    path('', CourierRiderListAPIView.as_view(), name='courier-rider-list'),
    path('<int:pk>/status/', CourierRiderStatusUpdateAPIView.as_view(), name='courier-rider-status-update'),
    path('<int:pk>/', CourierRiderDetailAPIView.as_view(), name='courier-rider-detail'),
    path('assignments/active/', ActiveRiderAssignmentListAPIView.as_view(), name='active-rider-assignments'),
    path('assignments/orders/assignable/', AssignableOnlineOrderListAPIView.as_view(), name='assignable-online-order-list'),
    path('assignments/orders/bulk/', BulkAssignOrdersAPIView.as_view(), name='bulk-assign-orders'),
]
