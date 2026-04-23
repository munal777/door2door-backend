from django.urls import path
from .views import (
    WeightSlabListCreateAPIView,
    WeightSlabDetailAPIView,
    ServiceTypePricingListCreateAPIView,
    ServiceTypePricingDetailAPIView,
    LocationPricingListCreateAPIView,
    LocationPricingDetailAPIView,
    LocationListAPIView,
    PriceEstimationAPIView,
)

app_name = 'pricings'

urlpatterns = [
    path('admin/weight-slabs/', WeightSlabListCreateAPIView.as_view(), name='weight-slab-list-create'),
    path('admin/weight-slabs/<int:pk>/', WeightSlabDetailAPIView.as_view(), name='weight-slab-detail'),
    path('admin/service-types/', ServiceTypePricingListCreateAPIView.as_view(), name='service-type-list-create'),
    path('admin/service-types/<int:pk>/', ServiceTypePricingDetailAPIView.as_view(), name='service-type-detail'),
    path('admin/locations/', LocationPricingListCreateAPIView.as_view(), name='location-pricing-list-create'),
    path('admin/locations/<int:pk>/', LocationPricingDetailAPIView.as_view(), name='location-pricing-detail'),
    path('locations/', LocationListAPIView.as_view(), name='location-list'),
    path('estimate/', PriceEstimationAPIView.as_view(), name='price-estimation'),
]
