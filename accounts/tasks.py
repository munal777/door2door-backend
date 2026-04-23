from django.tasks import task
from celery import shared_task
from accounts.services import (
    send_provider_approval_email,
    send_provider_rejection_email,
    send_otp_email_service,
    send_provider_invitation_email,
)

from accounts.models.invitation import ProviderInvitation
from accounts.models.provider import CourierProvider

@shared_task(bind=True, max_retries=0)
def send_approval_email(self, provider_id, email, password):
    """
    Async task to send approval email to courier provider.
    """

    courier = CourierProvider.objects.get(id=provider_id)
    return send_provider_approval_email(courier, email, password)


@shared_task(bind=True, max_retries=0)
def send_rejection_email(self, provider_id, rejection_reason):
    """
    Async task to send rejection email to courier provider.
    """

    courier = CourierProvider.objects.get(id=provider_id)
    return send_provider_rejection_email(courier, rejection_reason)


@shared_task(bind=True, max_retries=0)
def send_otp_email(self, email, otp_code):
    """
    Async task to send OTP email for verification.
    """
    return send_otp_email_service(email, otp_code)

@shared_task(bind=True, max_retries=0)
def send_invitation_email(self, invitation_id):
    """
    Async task to send email for invitation.
    """
    invitation = ProviderInvitation.objects.get(id=invitation_id)
    return send_provider_invitation_email(invitation)