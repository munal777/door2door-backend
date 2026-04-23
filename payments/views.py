import base64
import json
from urllib.parse import urlencode

from decimal import Decimal

from rest_framework import generics, status
from rest_framework.views import APIView

from django.shortcuts import get_object_or_404
from django.db import transaction as db_transaction
from django.conf import settings
from django.urls import reverse

from orders.models import Order
from .http import HttpResponsePermanentRedirect as MobileHttpResponsePermanentRedirect
from .models import Transaction
from .serializers import EsewaPaymentInitSerializer
from .utils import build_signed_string_from_fields, generate_esewa_signature, generate_transaction_uuid
from .services import PaymentService
from myproject.utils import api_response


class EsewaPaymentInitAPIView(generics.CreateAPIView):
    """
    Initialize eSewa payment for online order
    """
    serializer_class = EsewaPaymentInitSerializer
    lookup_field = 'order_number'

    def create(self, request, *args, **kwargs):
        user = request.user
        order_number = kwargs.get('order_number')
        
        # Fetch the order
        order = get_object_or_404(Order, order_number=order_number, consumer=user)

        if order.payment_method != Order.PaymentMethod.ESEWA:
            return api_response(
                is_success=False,
                error_message="This order is not configured for eSewa payment.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if order.payment_status == Order.PaymentStatus.PAID:
            return api_response(
                is_success=False,
                error_message="This order is already paid.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        # Use order's total price as payment amount
        total_amount = Decimal(str(order.total_price))
        currency = "NPR"
        
        # Calculate breakdown from total amount
        tax_amount = Decimal("0")
        service_charge = Decimal("0")
        delivery_charge = Decimal("0")

        transaction_uuid = generate_transaction_uuid()
        product_code = settings.ESEWA_MERCHANT_CODE

        with db_transaction.atomic():
            Transaction.objects.create(
                user=user,
                transaction_uuid=transaction_uuid,
                total_amount=total_amount,
                tax_amount=tax_amount,
                service_charge=service_charge,
                currency=currency,
                status=Transaction.STATUS_CHOICES.PENDING,
                provider=Transaction.PROVIDERS.ESEWA,
                metadata={
                    "product_code": product_code,
                    "order_number": order_number,
                    "order_id": order.id,
                }
            )
        

        # Prepare eSewa signature - must match official eSewa format
        signed_field_names = ["total_amount", "transaction_uuid", "product_code"]
        data_to_sign = {
            "total_amount": str(total_amount),
            "transaction_uuid": transaction_uuid,
            "product_code": product_code,
        }

        # 1. Build string to sign
        signed_string = build_signed_string_from_fields(signed_field_names, data_to_sign)

        # 2. Generate signature
        signature = generate_esewa_signature(settings.ESEWA_SECRET_KEY, signed_string)

        callback_url = settings.ESEWA_PAYMENT_CALLBACK_URL

        esewa_payload = {
            "amount": str(total_amount),
            "tax_amount": str(tax_amount),
            "total_amount": str(total_amount),
            "transaction_uuid": transaction_uuid,
            "product_code": product_code,
            "product_service_charge": str(service_charge),
            "product_delivery_charge": str(delivery_charge),
            "success_url": callback_url,
            "failure_url": callback_url,
            "signed_field_names": "total_amount,transaction_uuid,product_code",
            "signature": signature
        }

        return api_response(
            result = {
                "esewa_payload": esewa_payload,
                "esewa_form_url": settings.ESEWA_UAT_BASE_URL,
            },
            is_success=True,
            status_code=status.HTTP_200_OK
        )
    


class EsewaPaymentVerifyView(APIView):
    """
    Verify eSewa callback data and redirect back to the mobile app.
    """
    def _build_mobile_redirect_url(
        self,
        *,
        status_value,
        message,
        transaction_uuid=None,
        order_number=None,
        transaction_code=None,
    ):
        mobile_return_url = settings.PAYMENT_MOBILE_CALLBACK_URL

        query_params = {
            "status": status_value,
            "message": message,
        }
        if transaction_uuid:
            query_params["transaction_uuid"] = transaction_uuid
        if order_number:
            query_params["order_number"] = order_number
        if transaction_code:
            query_params["transaction_code"] = transaction_code

        joiner = "&" if "?" in mobile_return_url else "?"
        return f"{mobile_return_url}{joiner}{urlencode(query_params)}"

    def _redirect_to_mobile_app(
        self,
        *,
        status_value,
        message,
        transaction_uuid=None,
        order_number=None,
        transaction_code=None,
    ):
        redirect_url = self._build_mobile_redirect_url(
            status_value=status_value,
            message=message,
            transaction_uuid=transaction_uuid,
            order_number=order_number,
            transaction_code=transaction_code,
        )
        return MobileHttpResponsePermanentRedirect(redirect_url)

    def get(self, request):
        data_encoded = request.GET.get("data")
        if not data_encoded:
            return self._redirect_to_mobile_app(
                status_value="failed",
                message="No data received",
            )

        try:
            data_json = base64.b64decode(data_encoded).decode("utf-8")
            payment_data = json.loads(data_json)

            transaction_uuid = payment_data.get("transaction_uuid")

            transaction_obj = get_object_or_404(Transaction, transaction_uuid=transaction_uuid)

            signed_field_names = [
                "transaction_code",
                "status",
                "total_amount",
                "transaction_uuid",
                "product_code",
                "signed_field_names",
            ]
            
            received_signature = payment_data.get("signature")
            data_to_verify = {k: payment_data.get(k, "") for k in signed_field_names}
            signed_string = build_signed_string_from_fields(signed_field_names, data_to_verify)
            expected_signature = generate_esewa_signature(settings.ESEWA_SECRET_KEY, signed_string)

            if received_signature != expected_signature:
                # Signature verification failed
                result = PaymentService.handle_payment_failure(
                    transaction_obj,
                    payment_data,
                    "Signature verification failed"
                )
                return self._redirect_to_mobile_app(
                    status_value="failed",
                    message=result["message"],
                    transaction_uuid=transaction_uuid,
                    order_number=transaction_obj.metadata.get("order_number"),
                )

            result = PaymentService.handle_payment_completion(transaction_obj, payment_data)

            if result["success"]:
                return self._redirect_to_mobile_app(
                    status_value="success",
                    message=result["message"],
                    transaction_uuid=transaction_uuid,
                    order_number=result.get("order_number"),
                    transaction_code=result.get("transaction_code"),
                )
            else:

                if payment_data.get("status") != "COMPLETE":
                    PaymentService.handle_payment_failure(
                        transaction_obj,
                        payment_data
                    )

                return self._redirect_to_mobile_app(
                    status_value="failed",
                    message=result["message"],
                    transaction_uuid=transaction_uuid,
                    order_number=transaction_obj.metadata.get("order_number"),
                )

        except json.JSONDecodeError:
            return self._redirect_to_mobile_app(
                status_value="failed",
                message="Invalid payment data format",
            )

        except Exception as e:
            return self._redirect_to_mobile_app(
                status_value="failed",
                message=f"Payment verification error: {str(e)}",
            )

