from rest_framework import generics, permissions, status

from myproject.permissions import IsCourierAdmin
from myproject.utils import api_response
from orders.paginations import StandardResultsSetPagination

from .models import Invoice
from .serializers import InvoiceDetailSerializer, InvoiceListSerializer


class InvoiceListAPIView(generics.ListAPIView):
	"""
	List invoices for the authenticated courier company manager.
	Supports filtering by status and issue date range.
	"""

	serializer_class = InvoiceListSerializer
	permission_classes = [permissions.IsAuthenticated, IsCourierAdmin]
	pagination_class = StandardResultsSetPagination

	def get_queryset(self):
		queryset = Invoice.objects.filter(
			courier_provider=self.request.courier,
		).select_related('order', 'courier_provider')

		invoice_status = self.request.query_params.get('status')
		if invoice_status:
			queryset = queryset.filter(status=invoice_status)

		date_from = self.request.query_params.get('date_from')
		date_to = self.request.query_params.get('date_to')
		if date_from:
			queryset = queryset.filter(issue_date__gte=date_from)
		if date_to:
			queryset = queryset.filter(issue_date__lte=date_to)

		invoice_number = self.request.query_params.get('invoice_number')
		if invoice_number:
			queryset = queryset.filter(invoice_number__icontains=invoice_number)

		order_number = self.request.query_params.get('order_number')
		if order_number:
			queryset = queryset.filter(order__order_number__icontains=order_number)

		return queryset

	def list(self, request, *args, **kwargs):
		queryset = self.filter_queryset(self.get_queryset())
		page = self.paginate_queryset(queryset)

		if page is not None:
			serializer = self.get_serializer(page, many=True)
			paginated_response = self.paginator.get_paginated_response(serializer.data)
			return api_response(
				result=paginated_response.data,
				is_success=True,
				status_code=status.HTTP_200_OK,
			)

		serializer = self.get_serializer(queryset, many=True)
		return api_response(
			result=serializer.data,
			is_success=True,
			status_code=status.HTTP_200_OK,
		)


class InvoiceDetailAPIView(generics.RetrieveAPIView):
	"""
	Retrieve details for one invoice belonging to the authenticated manager's courier company.
	"""

	serializer_class = InvoiceDetailSerializer
	permission_classes = [permissions.IsAuthenticated, IsCourierAdmin]
	lookup_field = 'invoice_number'

	def get_queryset(self):
		return Invoice.objects.filter(
			courier_provider=self.request.courier,
		).select_related('order', 'courier_provider')

	def retrieve(self, request, *args, **kwargs):
		invoice = self.get_object()
		serializer = self.get_serializer(invoice)
		return api_response(
			result=serializer.data,
			is_success=True,
			status_code=status.HTTP_200_OK,
		)
