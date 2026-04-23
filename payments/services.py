from django.db import transaction as db_transaction
from orders.models import Order
from .models import Transaction


class PaymentService:
    """Service for handling payment operations and order updates"""
    
    @staticmethod
    def handle_payment_completion(transaction_obj, payment_data):
        """
        Handle successful payment completion.
        Updates transaction status and order payment status to PAID.
        """
        transaction_code = payment_data.get("transaction_code")
        payment_status = payment_data.get("status")
        
        if payment_status != "COMPLETE":
            return {
                "success": False,
                "message": f"Payment not complete. Status: {payment_status}"
            }
        
        try:
            with db_transaction.atomic():
                # Update transaction to SUCCESS
                transaction_obj.status = Transaction.STATUS_CHOICES.SUCCESS
                transaction_obj.provider_reference = transaction_code
                transaction_obj.metadata.update({
                    "esewa_response": payment_data,
                    "verified_at": str(transaction_obj.updated_at)
                })
                transaction_obj.save()
                
                # Update order payment status to PAID
                order_number = transaction_obj.metadata.get("order_number")
                if order_number:
                    updated_orders = Order.objects.filter(
                        order_number=order_number
                    ).update(
                        payment_method=Order.PaymentMethod.ESEWA,
                        payment_status=Order.PaymentStatus.PAID
                    )
                    
                    if updated_orders == 0:
                        return {
                            "success": False,
                            "message": f"Order {order_number} not found"
                        }
                    
                    return {
                        "success": True,
                        "message": "Payment completed and order updated successfully",
                        "transaction_code": transaction_code,
                        "order_number": order_number
                    }
                else:
                    return {
                        "success": False,
                        "message": "Order number not found in transaction metadata"
                    }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error processing payment completion: {str(e)}"
            }
    
    @staticmethod
    def handle_payment_failure(transaction_obj, payment_data, error_message=None):
        """
        Handle failed payment.
        Updates transaction status to FAILED and marks related order payment status as FAILED.
        """
        try:
            with db_transaction.atomic():
                transaction_obj.status = Transaction.STATUS_CHOICES.FAILED
                
                if error_message:
                    transaction_obj.metadata["error"] = error_message
                
                transaction_obj.metadata.update({
                    "esewa_response": payment_data,
                    "payment_status": payment_data.get("status")
                })
                transaction_obj.save()

                order_number = transaction_obj.metadata.get("order_number")
                if order_number:
                    Order.objects.filter(order_number=order_number).update(
                        payment_method=Order.PaymentMethod.ESEWA,
                        payment_status=Order.PaymentStatus.FAILED,
                    )
                
                return {
                    "success": False,
                    "message": error_message or "Payment verification failed",
                    "transaction_uuid": transaction_obj.transaction_uuid
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error processing payment failure: {str(e)}"
            }
