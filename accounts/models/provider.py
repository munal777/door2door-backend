from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.utils.translation import gettext_lazy as _
from django.utils.crypto import get_random_string

from .user import User
from .document import DocumentVerification

class CourierProvider(models.Model):
    """
    Courier Company (SaaS Client) Model.
    Represents a courier/logistics company that uses our platform as a SaaS solution.
    """

    class OperationalStatus(models.TextChoices):
        """Company operational status"""
        PENDING_DOCUMENTS = "pending_documents", _("Pending Document Submission")
        UNDER_REVIEW = "under_review", _("Under Review")
        ACTIVE = "active", _("Active")
        SUSPENDED = "suspended", _("Suspended")

    # Company Identity
    name = models.CharField(
        max_length=255,
        help_text=_("Legal company name")
    )

    logo = models.ImageField(
        upload_to='courier_providers/logos/',
        blank=True,
        null=True,
        help_text=_("Optional courier company logo")
    )

    company_email = models.EmailField(
        unique=True,
        help_text=_("Official company contact email")
    )
    company_phone = models.CharField(
        max_length=15,
        help_text=_("Official company contact phone")
    )
    
    # Company Address
    address_line = models.TextField(
        help_text=_("Street address of company headquarters")
    )
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    country = models.CharField(
        max_length=100,
        default="Nepal",
        help_text=_("Country of operation")
    )
    
    # Verification Status (derived from submitted documents)
    # This field represents the overall company operational status
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
        related_query_name='company'
    )
    
    # Operational Settings
    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether company can perform operations")
    )
    
    max_riders = models.PositiveIntegerField(
        default=15,
        help_text=_("Maximum number of riders allowed (subscription tier limit)")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Courier Provider")
        verbose_name_plural = _("Courier Providers")
        ordering = ['-created_at']
        indexes = [
            # models.Index(fields=['registration_number']),
            models.Index(fields=['operational_status']),
        ]

    def __str__(self):
        return self.name

    @property
    def is_verified(self):
        """Check if company is approved and verified based on required documents"""
        
        # Check if all required documents are approved
        required_docs = [
            DocumentVerification.DocumentType.COMPANY_REGISTRATION,
            DocumentVerification.DocumentType.COMPANY_PAN_VAT,
        ]
        
        for doc_type in required_docs:
            if not self.documents.filter(
                document_type=doc_type,
                status=DocumentVerification.VerificationStatus.APPROVED
            ).exists():
                return False
        
        return True

    @property
    def can_operate(self):
        """Check if company can perform business operations"""
        return (
            self.is_active and 
            self.operational_status == self.OperationalStatus.ACTIVE and 
            self.is_verified
        )

class CourierStaff(models.Model):
    """
    Staff Members of Courier Company.
    """

    class StaffRole(models.TextChoices):
        """Staff role types"""
        ADMIN = "admin", _("Admin")
        OPERATIONS = "operations", _("Operations Staff")

    ROLE_DEFAULT_PERMISSIONS = {
        StaffRole.ADMIN: {
            'can_manage_invitations': True,
            'can_manage_riders': True,
            'can_manage_orders': True,
            'can_manage_shippings': True,
            'can_manage_settings': True,
        },
        StaffRole.OPERATIONS: {
            'can_manage_invitations': False,
            'can_manage_riders': False,
            'can_manage_orders': True,
            'can_manage_shippings': True,
            'can_manage_settings': False,
        },
    }

    # Core Relationships
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='courier_staff_profile',
        help_text=_("User account for this staff member")
    )
    company = models.ForeignKey(
        CourierProvider,
        on_delete=models.CASCADE,
        related_name='staff_members',
        help_text=_("Courier company this staff belongs to")
    )
    
    # Role & Permissions
    role = models.CharField(
        max_length=20,
        choices=StaffRole.choices,
        default=StaffRole.OPERATIONS,
        help_text=_("Staff role determining access level")
    )
    
    # Granular Permissions (for Operations staff)
    can_manage_invitations = models.BooleanField(
        default=False,
        help_text=_("Permission to add/edit/remove invitations")
    )
    can_manage_riders = models.BooleanField(
        default=False,
        help_text=_("Permission to manage riders")
    )
    can_manage_orders = models.BooleanField(
        default=True,
        help_text=_("Permission to view and manage orders")
    )
    can_manage_shippings = models.BooleanField(
        default=True,
        help_text=_("Permission to view and manage shippings")
    )
    can_manage_settings = models.BooleanField(
        default=False,
        help_text=_("Permission to modify company settings")
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether staff member is active")
    )
    

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Courier Staff")
        verbose_name_plural = _("Courier Staff")
        unique_together = [('user', 'company')]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'role']),
        ]

    def __str__(self):
        return f"{self.user.full_name} ({self.get_role_display()}) - {self.company.name}"

    @property
    def is_admin(self):
        """Check if staff member is an admin"""
        return self.role == self.StaffRole.ADMIN

    def has_permission(self, permission):
        """
        Check if staff has a specific permission.           
        """
        # Admins have all permissions
        if self.is_admin:
            return True
        
        # Check specific permission
        permission_map = {
            'manage_invitations': self.can_manage_invitations,
            'manage_riders': self.can_manage_riders,
            'manage_shippings': self.can_manage_shippings,
            'manage_orders': self.can_manage_orders,
            'manage_settings': self.can_manage_settings,
        }
        
        return permission_map.get(permission, False)

    def apply_role_defaults(self):
        """Set default permissions based on the current role."""
        defaults = self.ROLE_DEFAULT_PERMISSIONS.get(self.role, {})
        for field_name, value in defaults.items():
            setattr(self, field_name, value)

    def save(self, *args, **kwargs):
        role_changed = False
        if self.pk:
            previous_role = (
                CourierStaff.objects.filter(pk=self.pk)
                .values_list('role', flat=True)
                .first()
            )
            role_changed = previous_role is not None and previous_role != self.role

        if not self.pk or role_changed:
            self.apply_role_defaults()

        super().save(*args, **kwargs)