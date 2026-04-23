from datetime import date

from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from rest_framework import serializers

from accounts.models.rider import Rider
from accounts.models.invitation import ProviderInvitation
from accounts.models.document import DocumentVerification
from .auth import UserRegisrationSerializer

User = get_user_model()


class RiderDocumentUploadSerializer(serializers.Serializer):
    """Serializer for individual document upload during rider registration"""
    document_type = serializers.ChoiceField(choices=DocumentVerification.DocumentType.choices)
    document_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    uploaded_file = serializers.FileField()

    def validate_document_type(self, value):
        """Ensure only rider-related documents are accepted"""
        rider_doc_types = [
            DocumentVerification.DocumentType.RIDER_DRIVING_LICENSE,
            DocumentVerification.DocumentType.RIDER_ID_PROOF,
        ]
        
        if value not in rider_doc_types:
            raise serializers.ValidationError(
                "Invalid document type for rider registration."
            )
        return value

    def validate_uploaded_file(self, value):
        """Validate file size and type"""
        # Maximum file size: 5MB
        max_size = 5 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError("File size cannot exceed 5MB.")
        
        # Allowed file types
        allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                "Only PDF, JPEG, and PNG files are allowed."
            )
        
        return value


class RiderRegistrationSerializer(serializers.Serializer):
    """
    Serializer for rider registration with invitation token.
    Riders must provide a valid invitation token from their courier company.
    """
    
    # Invitation Token
    invitation_token = serializers.CharField(
        max_length=64,
        write_only=True
    )
    
    user = UserRegisrationSerializer(write_only=True)
    documents = RiderDocumentUploadSerializer(many=True, write_only=True)
    
    # Rider Personal Information
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    emergency_contact_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    emergency_contact_phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    
    # Vehicle Information
    vehicle_type = serializers.ChoiceField(choices=Rider.VehicleType.choices)
    vehicle_number = serializers.CharField(max_length=50)
    vehicle_model = serializers.CharField(max_length=100, required=False, allow_blank=True)
    vehicle_color = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate_invitation_token(self, value):
        """Validate that the invitation token exists and is valid"""
        
        try:
            invitation = ProviderInvitation.objects.select_related('courier_provider').get(
                invitation_token=value
            )
            
            # Check if invitation is valid
            if not invitation.is_valid():
                if invitation.status == ProviderInvitation.InvitationStatus.ACCEPTED:
                    raise serializers.ValidationError(
                        "This invitation has already been used."
                    )
                elif invitation.status == ProviderInvitation.InvitationStatus.EXPIRED or invitation.is_expired:
                    raise serializers.ValidationError(
                        "This invitation has expired. Please request a new invitation from your courier company."
                    )
                elif invitation.status == ProviderInvitation.InvitationStatus.REVOKED:
                    raise serializers.ValidationError(
                        "This invitation has been revoked. Please contact your courier company."
                    )
                else:
                    raise serializers.ValidationError(
                        "This invitation is no longer valid."
                    )
            
            # Check if courier is active
            if not invitation.courier_provider.is_active:
                raise serializers.ValidationError(
                    "The courier company is currently inactive. Please contact them for more information."
                )

            # Ensure the token is meant for rider onboarding
            if invitation.role != ProviderInvitation.InvitationRole.RIDER:
                raise serializers.ValidationError(
                    "This invitation token is not authorized for rider registration."
                )
            
            # Check if courier can onboard more riders
            current_riders = Rider.objects.filter(company=invitation.courier_provider).count()
            if current_riders >= invitation.courier_provider.max_riders:
                raise serializers.ValidationError(
                    "This courier company has reached its maximum rider capacity."
                )
            
            # Store invitation in context for use in create method
            self.context['invitation'] = invitation
            
        except ProviderInvitation.DoesNotExist:
            raise serializers.ValidationError(
                "Invalid invitation token. Please check your email link."
            )
        
        return value
    
    def validate_vehicle_number(self, value):
        if Rider.objects.filter(vehicle_number=value).exists():
            raise serializers.ValidationError(
                "Vehicle number already registered."
            )
        
        return value


    def validate(self, data):
        """Cross-field validation"""
        # Age validation (if date_of_birth provided)
        if data.get('date_of_birth'):
            age = (date.today() - data['date_of_birth']).days // 365
            if age < 18:
                raise serializers.ValidationError({
                    'date_of_birth': "Rider must be at least 18 years old."
                })
            if age > 70:
                raise serializers.ValidationError({
                    'date_of_birth': "Invalid date of birth."
                })
        
        # Email validation - must match invitation email
        invitation = self.context.get('invitation')
        if invitation:
            user_email = data['user'].get("email")
            if user_email != invitation.email:
                raise serializers.ValidationError({
                    'user': {
                        'email': f"Email must match the invitation email: {invitation.email}"
                    }
                })
        
        return data

    @transaction.atomic
    def create(self, validated_data):
        """Create user account and rider profile"""
        
        # Extract data
        validated_data.pop('invitation_token', None)
        user_data = validated_data.pop('user')
        documents_data = validated_data.pop('documents', [])
        
        # Get invitation from context (already validated)
        invitation = self.context.get('invitation')
        
        if not invitation:
            raise serializers.ValidationError("Invitation not found in context.")
        
        # Get courier company from invitation
        courier = invitation.courier_provider
        
        # Create user using nested serializer
        user_serializer = UserRegisrationSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user_instance = user_serializer.save(user_type=User.UserType.RIDER, is_active=True)
        
        # Create rider profile
        rider = Rider.objects.create(
            user=user_instance,
            company=courier,
            **validated_data
        )
        
        # Upload documents if provided
        if documents_data:
            content_type = ContentType.objects.get_for_model(Rider)
            for doc_data in documents_data:
                DocumentVerification.objects.create(
                    content_type=content_type,
                    object_id=rider.id,
                    document_type=doc_data['document_type'],
                    document_number=doc_data.get('document_number', ''),
                    uploaded_file=doc_data['uploaded_file'],
                    status=DocumentVerification.VerificationStatus.PENDING
                )
        
        # Mark invitation as accepted
        if not invitation.accept():
            raise serializers.ValidationError("This invitation is no longer valid.")
        
        return rider


class RiderDetailSerializer(serializers.ModelSerializer):
    """Detailed rider information serializer"""
    
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = Rider
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone_number', 'company_name', 'date_of_birth',
            'emergency_contact_name', 'emergency_contact_phone',
            'vehicle_type', 'vehicle_number', 'vehicle_model', 'vehicle_color',
            'operational_status', 'availability_status',
        ]
        read_only_fields = ['id']
    
    def get_documents_count(self, obj):
        """Get count of submitted documents"""
        return obj.documents.count()
