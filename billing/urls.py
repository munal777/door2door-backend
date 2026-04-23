from django.urls import path

from .views import (
    InvoiceDetailAPIView,
    InvoiceListAPIView,
)

app_name = 'billing'

urlpatterns = [
    path('invoices/', InvoiceListAPIView.as_view(), name='invoice-list'),
    path('invoices/<str:invoice_number>/', InvoiceDetailAPIView.as_view(), name='invoice-detail'),
]
