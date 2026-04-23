from django.utils import timezone
from rest_framework import serializers

from accounts.models.invitation import ProviderInvitation
from accounts.models.provider import CourierProvider
from accounts.models.user import User
from myproject.utils import format_datetime


class SendInvitationSerializer(serializers.Serializer):
    """
    Serializer for sending provider invitations.
    Provider admin can send invitation to a rider or staff via email.
    """
    email = serializers.EmailField(
        help_text="Email address of the user to invite"
    )
    role = serializers.ChoiceField(
        choices=ProviderInvitation.InvitationRole.choices,
        help_text="Role to assign (rider, admin, operations)"
    )

    def validate_email(self, value):
        """Validate email"""
        # Check if there's already a pending invitation for this email
        courier_provider = self.context.get('courier_provider')
        
        if not courier_provider:
            raise serializers.ValidationError("Courier provider not found in context.")
        
        # Check if email already exists in User model
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "This email is already registered in the system. "
                "The user may already have an account."
            )
        
        # Check for existing pending invitation
        existing_invitation = ProviderInvitation.objects.filter(
            courier_provider=courier_provider,
            email=value,
            status=ProviderInvitation.InvitationStatus.PENDING,
            expires_at__gt=timezone.now()
        ).first()
        
        if existing_invitation:
            raise serializers.ValidationError(
                f"An active invitation already exists for this email. "
                f"It will expire at {format_datetime(existing_invitation.expires_at)}."
            )
        
        return value

    def validate(self, data):
        """Cross-field validation"""
        courier_provider = self.context.get('courier_provider')
        
        # Check if courier can onboard more riders (only for RIDER role)
        role = data.get('role')
        if role == ProviderInvitation.InvitationRole.RIDER:
            current_riders = courier_provider.riders.count()
            if current_riders >= courier_provider.max_riders:
                raise serializers.ValidationError(
                    "Your company has reached its maximum rider capacity. "
                    "Please contact support to increase your rider limit."
                )
        
        return data

    def create(self, validated_data):
        """Create invitation"""
        courier_provider = self.context.get('courier_provider')
        invited_by = self.context.get('invited_by')
        
        invitation = ProviderInvitation.objects.create(
            courier_provider=courier_provider,
            email=validated_data['email'],
            role=validated_data['role'],
            invited_by=invited_by
        )
        
        return invitation


class InvitationTokenValidationSerializer(serializers.Serializer):
    """
    Serializer to validate invitation token before registration starts.
    """

    invitation_token = serializers.CharField(
        max_length=64,
        help_text="Invitation token received in the registration link"
    )
    registration_type = serializers.ChoiceField(
        choices=[("staff", "Staff"), ("rider", "Rider")],
        required=False,
        help_text="Optional registration type guard for token role"
    )


class InvitationDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for provider invitation.
    """
    # courier_name = serializers.CharField(source='courier_provider.name', read_only=True)
    invited_by_name = serializers.SerializerMethodField()
    time_remaining_hours = serializers.SerializerMethodField()
    invited_at = serializers.SerializerMethodField()
    expires_at = serializers.SerializerMethodField()
    accepted_at = serializers.SerializerMethodField()

    class Meta:
        model = ProviderInvitation
        fields = [
            'id', 'email', 'role', 'status', 'invited_at', 'expires_at', 
            'accepted_at', 'invited_by_name', 'time_remaining_hours',
        ]
        read_only_fields = fields

    def get_invited_by_name(self, obj):
        """Get name of the person who sent invitation"""
        if obj.invited_by:
            return f"{obj.invited_by.first_name} {obj.invited_by.last_name}".strip()
        return "System"

    def get_time_remaining_hours(self, obj):
        """Get remaining time in hours"""
        if obj.is_expired:
            return 0
        time_remaining = obj.time_remaining
        return round(time_remaining.total_seconds() // 3600, 2)
    
    def get_invited_at(self, obj):
        """Format invited_at datetime"""
        return format_datetime(obj.invited_at)
    
    def get_expires_at(self, obj):
        """Format expires_at datetime"""
        return format_datetime(obj.expires_at)
    
    def get_accepted_at(self, obj):
        """Format accepted_at datetime"""
        return format_datetime(obj.accepted_at)

class InvitationListSerializer(serializers.ModelSerializer):
    """
    List serializer for provider invitations.
    Used for listing invitations by provider.
    """
    invited_by_name = serializers.SerializerMethodField()
    time_remaining_hours = serializers.SerializerMethodField()
    invited_at = serializers.SerializerMethodField()
    expires_at = serializers.SerializerMethodField()

    class Meta:
        model = ProviderInvitation
        fields = [
            'id', 'email', 'role', 'status', 'invited_at',
            'expires_at', 'invited_by_name', 'time_remaining_hours'
        ]

    def get_invited_by_name(self, obj):
        """Get name of the person who sent invitation"""
        if obj.invited_by:
            return f"{obj.invited_by.first_name} {obj.invited_by.last_name}".strip()
        return "System"

    def get_time_remaining_hours(self, obj):
        """Get remaining time in hours"""
        if obj.is_expired:
            return 0
        time_remaining = obj.time_remaining
        return round(time_remaining.total_seconds() // 3600, 2)
    
    def get_invited_at(self, obj):
        """Format invited_at datetime"""
        return format_datetime(obj.invited_at)
    
    def get_expires_at(self, obj):
        """Format expires_at datetime"""
        return format_datetime(obj.expires_at)