from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from datetime import timedelta

from .provider import CourierProvider


class ProviderInvitation(models.Model):
    """
    Invitation model for adding riders and courier staff.
    Invitation is valid for 72 hours.
    """

    class InvitationRole(models.TextChoices):
        """Roles that can be invited"""
        RIDER = "rider", _("Rider")
        ADMIN = "admin", _("Courier Admin")
        OPERATIONS = "operations", _("Operations Staff")

    class InvitationStatus(models.TextChoices):
        """Invitation status choices"""
        PENDING = "pending", _("Pending")
        ACCEPTED = "accepted", _("Accepted")
        EXPIRED = "expired", _("Expired")
        REVOKED = "revoked", _("Revoked")

    courier_provider = models.ForeignKey(
        CourierProvider,
        on_delete=models.CASCADE,
        related_name='rider_invitations',
        help_text=_("Courier provider sending the invitation")
    )
    
    email = models.EmailField(
        help_text=_("Email address of the invited user")
    )
    
    role = models.CharField(
        max_length=20,
        choices=InvitationRole.choices,
        default=InvitationRole.RIDER,
        help_text=_("Role to be assigned to the invited user")
    )
    
    invitation_token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text=_("Unique token for invitation link")
    )
    
    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_index=True,
        help_text=_("Current status of invitation")
    )
    
    invited_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_("When the invitation was sent")
    )
    
    expires_at = models.DateTimeField(
        help_text=_("When the invitation expires (72 hours from creation)")
    )
    
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When the invitation was accepted")
    )
    
    invited_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_invitations',
        help_text=_("Provider admin who sent the invitation")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invitation_token', 'status']),
            models.Index(fields=['courier_provider', 'status']),
            models.Index(fields=['email', 'status']),
        ]
        verbose_name = _("Provider Invitation")
        verbose_name_plural = _("Provider Invitations")

    def __str__(self):
        return f"Invitation to {self.email} ({self.get_role_display()}) by {self.courier_provider.name}"

    def save(self, *args, **kwargs):
        """Override save to generate token and set expiry"""
        if not self.invitation_token:
            self.invitation_token = get_random_string(length=64)
        
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=72)
        
        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if invitation is still valid"""
        if self.status != self.InvitationStatus.PENDING:
            return False
        
        if timezone.now() > self.expires_at:
            # Auto-expire if time has passed
            self.status = self.InvitationStatus.EXPIRED
            self.save(update_fields=['status', 'updated_at'])
            return False
        
        return True

    def accept(self):
        """Mark invitation as accepted"""
        if self.is_valid():
            self.status = self.InvitationStatus.ACCEPTED
            self.accepted_at = timezone.now()
            self.save(update_fields=['status', 'accepted_at', 'updated_at'])
            return True
        return False

    def revoke(self):
        """Revoke the invitation"""
        if self.status == self.InvitationStatus.PENDING:
            self.status = self.InvitationStatus.REVOKED
            self.save(update_fields=['status', 'updated_at'])
            return True
        return False

    @property
    def is_expired(self):
        """Check if invitation has expired"""
        return timezone.now() > self.expires_at

    @property
    def time_remaining(self):
        """Get remaining time for invitation"""
        if self.is_expired:
            return timedelta(0)
        return self.expires_at - timezone.now()
