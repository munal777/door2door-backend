from django.urls import path

from .views import EsewaPaymentInitAPIView, EsewaPaymentVerifyView


urlpatterns = [
	path(
		"esewa/init/<str:order_number>/",
		EsewaPaymentInitAPIView.as_view(),
		name="esewa-payment-init",
	),
	path(
		"esewa/verify/",
		EsewaPaymentVerifyView.as_view(),
		name="esewa-payment-verify",
	),
]
