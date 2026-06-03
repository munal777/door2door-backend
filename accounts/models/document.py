from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone

from myproject.storage import ProofOfDeliveryStorage, DocumentStorage


class DocumentVerification(models.Model):
    """
    Generic document verification model for storing and tracking documents 
    submitted by courier companies and riders.
    """

    class DocumentType(models.TextChoices):
        """Types of documents that can be uploaded"""
        # Courier Company Documents
        COMPANY_PAN_VAT = "company_pan_vat", _("Company PAN/VAT Number")
        COMPANY_REGISTRATION = "company_registration", _("Company Registration Certificate")
        COMPANY_ADDITIONAL = "company_additional", _("Additional Company Document")
        
        # Rider Documents
        RIDER_DRIVING_LICENSE = "rider_driving_license", _("Driving License")
        RIDER_ID_PROOF = "rider_id_proof", _("National ID/Citizenship")
        RIDER_VEHICLE_REGISTRATION = "rider_vehicle_registration", _("Vehicle Registration")

    class VerificationStatus(models.TextChoices):
        """Document verification status"""
        PENDING = "pending", _("Pending Review")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        EXPIRED = "expired", _("Expired")

    # Document Information
    document_type = models.CharField(
        max_length=50,
        choices=DocumentType.choices,
        db_index=True,
        help_text=_("Type of document uploaded")
    )
    document_number = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Document identification number")
    )
    uploaded_file = models.FileField(
        storage=DocumentStorage(),
        help_text=_("Uploaded document file (PDF, JPG, PNG)")
    )
    
    # Generic Foreign Key (Proper way to link to different models)
    # This uses Django's ContentTypes framework to avoid ID conflicts
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': ('courierprovider', 'rider')},
        help_text=_("Type of entity (CourierProvider or Rider)")
    )
    object_id = models.PositiveIntegerField(
        help_text=_("ID of the associated entity")
    )
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Verification Workflow
    status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        db_index=True,
        help_text=_("Current verification status")
    )
    
    # Verification Details
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_documents',
        limit_choices_to={'user_type': 'system_admin'},
        help_text=_("System Admin who verified this document")
    )
    verified_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("Timestamp when document was verified")
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text=_("Reason for rejection (if applicable)")
    )
    
    # Expiry Information (for documents like licenses)
    issue_date = models.DateField(
        blank=True,
        null=True,
        help_text=_("Document issue date")
    )
    expiry_date = models.DateField(
        blank=True,
        null=True,
        help_text=_("Document expiry date (if applicable)")
    )
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Document Verification")
        verbose_name_plural = _("Document Verifications")
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['status']),
            models.Index(fields=['document_type']),
        ]

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.get_status_display()}"

    @property
    def is_approved(self):
        """Check if document is approved"""
        return self.status == self.VerificationStatus.APPROVED

    @property
    def is_pending(self):
        """Check if document is pending review"""
        return self.status == self.VerificationStatus.PENDING

    @property
    def is_expired(self):
        """Check if document has expired"""
        if self.expiry_date:
            return timezone.now().date() > self.expiry_date
        return False
