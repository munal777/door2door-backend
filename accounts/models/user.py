from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for Door2Door platform.
    This is the base authentication model for all user types in the system.
    """

    class UserType(models.TextChoices):
        """User role types in the platform"""
        CONSUMER = "consumer", _("Consumer")
        COURIER_STAFF = "courier_staff", _("Courier Staff")
        RIDER = "rider", _("Rider")
        SYSTEM_ADMIN = "admin", _("System Admin")
        SYSTEM_SUPER_ADMIN = "superadmin", _("System SuperAdmin")

    # Authentication & Identity
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(max_length=15,blank=True)

    # Role & Type
    user_type = models.CharField(
        max_length=30,
        choices=UserType.choices,
        default=UserType.CONSUMER,
        db_index=True,  # Indexed for performance on user type queries
        help_text=_("Type of user account")
    )

    # Status Flags
    is_active = models.BooleanField(
        default=True,
        help_text=_("Designates whether this user account is active")
    )
    is_verified = models.BooleanField(
        default=False,
        help_text=_("Designates whether user has verified their email")
    )
    is_staff = models.BooleanField(
        default=False,
        help_text=_("Designates whether user can access admin site")
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['user_type']),
        ]

    def __str__(self):
        return f"{self.email} ({self.get_user_type_display()})"

    @property
    def full_name(self):
        """Returns the full name of the user"""
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def is_courier_staff(self):
        """Check if user is courier staff (role determined by CourierStaff.role)"""
        return self.user_type == self.UserType.COURIER_STAFF