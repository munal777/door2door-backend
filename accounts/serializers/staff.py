from django.db import transaction
from django.contrib.auth import get_user_model

from rest_framework import serializers

from accounts.models.provider import CourierStaff
from accounts.models.invitation import ProviderInvitation
from accounts.serializers.auth import UserRegisrationSerializer
from myproject.utils import format_datetime

User = get_user_model()


class CourierStaffRegistrationSerializer(serializers.Serializer):
    """
    Serializer for Courier Staff registration using an invitation token.
    The staff must provide a valid invitation token meant for admins or operations.
    """
    
    # Invitation Token
    invitation_token = serializers.CharField(
        max_length=64,
        write_only=True
    )
    
    user = UserRegisrationSerializer(write_only=True)

    def validate_invitation_token(self, value):
        """Validate that the invitation token exists and is valid"""
        
        try:
            invitation = ProviderInvitation.objects.select_related('courier_provider').get(
                invitation_token=value
            )
            
            # Check if invitation is valid
            if not invitation.is_valid():
                if invitation.status == ProviderInvitation.InvitationStatus.ACCEPTED:
                    raise serializers.ValidationError("This invitation has already been used.")
                elif invitation.status == ProviderInvitation.InvitationStatus.EXPIRED or invitation.is_expired:
                    raise serializers.ValidationError("This invitation has expired. Please request a new invitation.")
                elif invitation.status == ProviderInvitation.InvitationStatus.REVOKED:
                    raise serializers.ValidationError("This invitation has been revoked. Please contact the courier company.")
                else:
                    raise serializers.ValidationError("This invitation is no longer valid.")
            
            # Check if courier is active
            if not invitation.courier_provider.is_active:
                raise serializers.ValidationError(
                    "The courier company is currently inactive. Please contact them for more information."
                )
            
            # Staff checks
            if invitation.role not in [ProviderInvitation.InvitationRole.ADMIN, ProviderInvitation.InvitationRole.OPERATIONS]:
                raise serializers.ValidationError(
                    "This invitation token is not authorized for staff registration."
                )
            
            # Store invitation in context for use in create method
            self.context['invitation'] = invitation
            
        except ProviderInvitation.DoesNotExist:
            raise serializers.ValidationError(
                "Invalid invitation token. Please check your email link."
            )
        
        return value

    def validate(self, data):
        """Cross-field validation"""
        
        # Email validation - must match invitation email
        invitation = self.context.get('invitation')
        if invitation:
            user_email = data['user'].get("email")
            if user_email.lower() != invitation.email.lower():
                raise serializers.ValidationError({
                    'user': {
                        'email': f"Email must match the invitation email: {invitation.email}"
                    }
                })
        
        return data

    @transaction.atomic
    def create(self, validated_data):
        """Create user account and staff profile"""
        invitation_token = validated_data.pop('invitation_token', None)
        user_data = validated_data.pop('user')

        if not invitation_token:
            raise serializers.ValidationError("Invitation token is required.")

        # Re-read with DB lock to prevent token reuse races.
        try:
            invitation = ProviderInvitation.objects.select_for_update().select_related(
                'courier_provider'
            ).get(invitation_token=invitation_token)
        except ProviderInvitation.DoesNotExist:
            raise serializers.ValidationError("Invalid invitation token.")

        if not invitation.is_valid():
            raise serializers.ValidationError("This invitation is no longer valid.")

        if invitation.role not in [
            ProviderInvitation.InvitationRole.ADMIN,
            ProviderInvitation.InvitationRole.OPERATIONS,
        ]:
            raise serializers.ValidationError(
                "This invitation token is not authorized for staff registration."
            )

        if user_data.get('email', '').lower() != invitation.email.lower():
            raise serializers.ValidationError(
                f"Email must match the invitation email: {invitation.email}"
            )
        
        # Get courier company from invitation
        courier = invitation.courier_provider
        
        # Create user using nested serializer
        user_serializer = UserRegisrationSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user_instance = user_serializer.save(user_type=User.UserType.COURIER_STAFF, is_active=True)
        
        # Map ProviderInvitation role to CourierStaff role
        role_map = {
            ProviderInvitation.InvitationRole.ADMIN: CourierStaff.StaffRole.ADMIN,
            ProviderInvitation.InvitationRole.OPERATIONS: CourierStaff.StaffRole.OPERATIONS,
        }
        staff_role = role_map.get(invitation.role, CourierStaff.StaffRole.OPERATIONS)

        # Create staff profile
        staff = CourierStaff.objects.create(
            user=user_instance,
            company=courier,
            role=staff_role
        )
        
        # Mark invitation as accepted
        invitation.accept()
        
        return staff


class StaffPermissionSnapshotSerializer(serializers.Serializer):
    can_manage_orders = serializers.BooleanField()
    can_manage_shippings = serializers.BooleanField()
    can_manage_riders = serializers.BooleanField()
    can_manage_invitations = serializers.BooleanField()
    can_manage_settings = serializers.BooleanField()


class CourierStaffListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    permissions = serializers.SerializerMethodField()
    joined_at = serializers.SerializerMethodField()

    class Meta:
        model = CourierStaff
        fields = [
            'id',
            'full_name',
            'email',
            'phone_number',
            'role',
            'is_active',
            'permissions',
            'joined_at',
        ]

    def get_permissions(self, obj):
        return {
            'can_manage_orders': obj.is_admin or obj.can_manage_orders,
            'can_manage_shippings': obj.is_admin or obj.can_manage_shippings,
            'can_manage_riders': obj.is_admin or obj.can_manage_riders,
            'can_manage_invitations': obj.is_admin or obj.can_manage_invitations,
            'can_manage_settings': obj.is_admin or obj.can_manage_settings,
        }

    def get_joined_at(self, obj):
        return format_datetime(obj.created_at)


class CourierStaffDetailSerializer(CourierStaffListSerializer):
    accessible_modules = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()

    class Meta(CourierStaffListSerializer.Meta):
        fields = CourierStaffListSerializer.Meta.fields + [
            'accessible_modules',
            'updated_at',
        ]

    def get_accessible_modules(self, obj):
        modules = ['Dashboard']

        if obj.is_admin or obj.can_manage_orders:
            modules.append('Orders')
        if obj.is_admin or obj.can_manage_shippings:
            modules.append('Shipments')
        if obj.is_admin or obj.can_manage_riders:
            modules.append('Riders')
        if obj.is_admin or obj.can_manage_invitations:
            modules.append('Invitations')
        if obj.is_admin or obj.can_manage_settings:
            modules.append('Settings')

        return modules

    def get_updated_at(self, obj):
        return format_datetime(obj.updated_at)


class CourierStaffRolePermissionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourierStaff
        fields = [
            'role',
            'is_active',
            'can_manage_orders',
            'can_manage_shippings',
            'can_manage_riders',
            'can_manage_invitations',
            'can_manage_settings',
        ]
        extra_kwargs = {
            'role': {'required': False},
            'is_active': {'required': False},
            'can_manage_orders': {'required': False},
            'can_manage_shippings': {'required': False},
            'can_manage_riders': {'required': False},
            'can_manage_invitations': {'required': False},
            'can_manage_settings': {'required': False},
        }

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('At least one field must be provided.')
        return attrs

    def update(self, instance, validated_data):
        role_changed = 'role' in validated_data and validated_data['role'] != instance.role

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Changing role applies role defaults first; custom overrides are applied below.
        instance.save()

        # Admins must always retain full permissions.
        if instance.is_admin:
            instance.apply_role_defaults()
            instance.save(
                update_fields=[
                    'can_manage_invitations',
                    'can_manage_riders',
                    'can_manage_orders',
                    'can_manage_shippings',
                    'can_manage_settings',
                    'updated_at',
                ]
            )
            return instance

        # For operations staff, explicit permission payload overrides defaults.
        permission_fields = [
            'can_manage_orders',
            'can_manage_shippings',
            'can_manage_riders',
            'can_manage_invitations',
            'can_manage_settings',
        ]
        custom_permission_payload = any(field in validated_data for field in permission_fields)

        if role_changed and custom_permission_payload:
            for field in permission_fields:
                if field in validated_data:
                    setattr(instance, field, validated_data[field])
            instance.save(update_fields=permission_fields + ['updated_at'])

        return instance
