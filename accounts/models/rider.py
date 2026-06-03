from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .user import User
from .provider import CourierProvider
from .document import DocumentVerification

from myproject.storage import ProfileStorage

class Rider(models.Model):
    """
    Courier Rider/Driver Model.
    Represents delivery personnel who work for a courier company.
    """

    class OperationalStatus(models.TextChoices):
        """Rider operational status"""
        PENDING_DOCUMENTS = "pending_documents", _("Pending Document Submission")
        UNDER_REVIEW = "under_review", _("Under Review")
        ACTIVE = "active", _("Active")
        SUSPENDED = "suspended", _("Suspended")
        INACTIVE = "inactive", _("Inactive")

    class VehicleType(models.TextChoices):
        """Types of vehicles used for delivery"""
        BIKE = "bike", _("Motorcycle/Bike")
        SCOOTER = "scooter", _("Scooter")
        BICYCLE = "bicycle", _("Bicycle")
        CAR = "car", _("Car")
        VAN = "van", _("Van")
        TRUCK = "truck", _("Small Truck")

    class AvailabilityStatus(models.TextChoices):
        """Rider real-time availability"""
        AVAILABLE = "available", _("Available")
        BUSY = "busy", _("On Delivery")
        OFFLINE = "offline", _("Offline")

    # Core Relationships
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='rider_profile',
        help_text=_("User account for this rider")
    )
    company = models.ForeignKey(
        CourierProvider,
        on_delete=models.CASCADE,
        related_name='riders',
        help_text=_("Courier company this rider belongs to")
    )
    
    date_of_birth = models.DateField(
        blank=True,
        null=True,
        help_text=_("Date of birth for age verification")
    )
    emergency_contact_name = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Emergency contact person name")
    )
    emergency_contact_phone = models.CharField(
        max_length=15,
        blank=True,
        help_text=_("Emergency contact phone number")
    )
    
    # Vehicle Information
    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices,
        help_text=_("Type of vehicle used for deliveries")
    )
    vehicle_number = models.CharField(
        max_length=50,
        unique=True,
        help_text=_("Vehicle registration/plate number")
    )
    vehicle_model = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Vehicle make and model")
    )
    vehicle_color = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Vehicle color for identification")
    )
    
    # Verification Status (derived from submitted documents)
    # Note: Actual document verification is handled via DocumentVerification model
    operational_status = models.CharField(
        max_length=30,
        choices=OperationalStatus.choices,
        default=OperationalStatus.PENDING_DOCUMENTS,
        db_index=True,
        help_text=_("Current operational status based on document verification")
    )
    
    # Document Verification (Generic Relation)
    documents = GenericRelation(
        'DocumentVerification',
        related_query_name='rider'
    )
    
    # Real-time Location & Availability
    availability_status = models.CharField(
        max_length=20,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.OFFLINE,
        db_index=True,
        help_text=_("Current availability for accepting orders")
    )
    current_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        help_text=_("Current GPS latitude")
    )
    current_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        help_text=_("Current GPS longitude")
    )
    last_location_update = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("Last time location was updated")
    )
    
    # Performance Metrics
    # average_rating = models.DecimalField(
    #     max_digits=3,
    #     decimal_places=2,
    #     default=0.00,
    #     validators=[MinValueValidator(0.00), MaxValueValidator(5.00)],
    #     help_text=_("Average customer rating (0-5)")
    # )
    # total_ratings = models.PositiveIntegerField(
    #     default=0,
    #     help_text=_("Total number of ratings received")
    # )
    # completed_deliveries = models.PositiveIntegerField(
    #     default=0,
    #     help_text=_("Total successful deliveries completed")
    # )
    
    # Profile
    profile_photo = models.ImageField(
        storage=ProfileStorage(),
        blank=True,
        null=True,
        help_text=_("Rider profile photo")
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Rider")
        verbose_name_plural = _("Riders")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'operational_status']),
            models.Index(fields=['availability_status']),
            models.Index(fields=['vehicle_number']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.vehicle_number}) - {self.company.name}"

    @property
    def full_name(self):
        """Returns rider display name from linked user profile."""
        if self.user_id and self.user:
            return self.user.full_name
        return "Rider"

    @property
    def is_verified(self):
        """Check if rider is approved and verified based on required documents"""
        
        # Check if all required documents are approved
        required_docs = [
            DocumentVerification.DocumentType.RIDER_DRIVING_LICENSE,
            DocumentVerification.DocumentType.RIDER_ID_PROOF,
        ]
        
        for doc_type in required_docs:
            if not self.documents.filter(
                document_type=doc_type,
                status=DocumentVerification.VerificationStatus.APPROVED
            ).exists():
                return False
        
        return True

    @property
    def is_available(self):
        """Check if rider is currently available for deliveries"""
        return (
            self.is_verified and
            self.user.is_active and
            self.availability_status == self.AvailabilityStatus.AVAILABLE
        )

    @property
    def can_accept_orders(self):
        """Check if rider can accept delivery orders"""
        return (
            self.user.is_active and
            self.operational_status == self.OperationalStatus.ACTIVE and
            self.is_verified and
            self.is_available and
            self.company.can_operate
        )

    def update_location(self, latitude, longitude):
        """
        Update rider's current location.
        
        Args:
            latitude: GPS latitude coordinate
            longitude: GPS longitude coordinate
        """
        
        self.current_latitude = latitude
        self.current_longitude = longitude
        self.last_location_update = timezone.now()
        self.save(update_fields=['current_latitude', 'current_longitude', 'last_location_update', 'updated_at'])

    def set_availability(self, status):
        """
        Update rider's availability status.
        
        Args:
            status: New availability status (from AvailabilityStatus choices)
        """
        if status in self.AvailabilityStatus.values:
            self.availability_status = status
            self.save(update_fields=['availability_status', 'updated_at'])

    # def update_rating(self, new_rating):
    #     """
    #     Update rider's average rating with a new rating.
        
    #     Args:
    #         new_rating: New rating value (1-5)
    #     """
    #     total_score = self.average_rating * self.total_ratings
    #     self.total_ratings += 1
    #     self.average_rating = (total_score + new_rating) / self.total_ratings
    #     self.save(update_fields=['average_rating', 'total_ratings', 'updated_at'])

    def get_documents(self):
        """Get all documents submitted by this rider"""
        return DocumentVerification.objects.filter(
            entity_type='rider',
            entity_id=self.id
        )

    @property
    def all_documents_approved(self):
        """Check if all required documents are approved"""
        documents = self.get_documents()
        if not documents.exists():
            return False
        return all(doc.is_approved for doc in documents)