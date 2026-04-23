from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from rest_framework import serializers

from accounts.models.provider import CourierProvider
from accounts.models.document import DocumentVerification

User = get_user_model()

class DocumentUploadSerializer(serializers.Serializer):
    """Serializer for individual document upload during courier registration"""
    document_type = serializers.ChoiceField(choices=DocumentVerification.DocumentType.choices)
    document_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    uploaded_file = serializers.FileField()

    def validate_document_type(self, value):
        """Ensure only company-related documents are accepted"""
        company_doc_types = [
            DocumentVerification.DocumentType.COMPANY_PAN_VAT,
            DocumentVerification.DocumentType.COMPANY_REGISTRATION,
            DocumentVerification.DocumentType.COMPANY_ADDITIONAL
        ]
        
        if value not in company_doc_types:
            raise serializers.ValidationError(
                "Invalid document type for courier provider registration. "
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


class CourierProviderRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for courier provider registration with documents.
    """
    
    documents = DocumentUploadSerializer(many=True, write_only=True)
    
    class Meta:
        model = CourierProvider
        fields = [
            'id',
            'name',
            'company_email',
            'company_phone',
            'address_line',
            'city',
            'state',
            'postal_code',
            'country',
            'documents',
            'operational_status',
            'created_at',
        ]
        read_only_fields = ['id', 'operational_status', 'created_at']

    def validate_documents(self, value):
        """Ensure required documents are provided"""
        if not value:
            raise serializers.ValidationError("At least one document is required.")
        
        # Check for required documents
        required_doc_types = [
            DocumentVerification.DocumentType.COMPANY_REGISTRATION,
            DocumentVerification.DocumentType.COMPANY_PAN_VAT,
        ]
        
        uploaded_types = [doc['document_type'] for doc in value]
        
        for required_type in required_doc_types:
            if required_type not in uploaded_types:
                raise serializers.ValidationError(
                    f"Required document '{required_type}' is missing. "
                    "Company Registration and PAN/VAT documents are mandatory."
                )
        
        return value

    def validate_name(self, value):
        """Ensure company name is unique"""
        company_name= value.strip()
        if CourierProvider.objects.filter(name=company_name).exists():
            raise serializers.ValidationError(
                "A courier provider with this company name already exists."
            )
        return value

    def validate_company_email(self, value):
        """Ensure company email is unique"""
        if CourierProvider.objects.filter(company_email=value).exists():
            raise serializers.ValidationError(
                "A courier provider with this email already exists."
            )
        return value
    
    def validate_company_phone(self, value):
        """Ensure company phone is unique"""
        if CourierProvider.objects.filter(company_phone=value).exists():
            raise serializers.ValidationError(
                "A courier provider with this phone number already exists."
            )
        return value

    @transaction.atomic
    def create(self, validated_data):
        """
        Create courier provider with documents.
        Status automatically set to UNDER_REVIEW (pending admin approval).
        """
        # Extract documents data
        documents_data = validated_data.pop('documents')
        
        # Set initial status to UNDER_REVIEW
        validated_data['operational_status'] = CourierProvider.OperationalStatus.UNDER_REVIEW
        
        # Create courier provider instance
        courier_provider = CourierProvider.objects.create(**validated_data)
        
        # Get ContentType for CourierProvider
        content_type = ContentType.objects.get_for_model(CourierProvider)
        
        # Create document verification records
        for doc_data in documents_data:
            DocumentVerification.objects.create(
                content_type=content_type,
                object_id=courier_provider.id,
                document_type=doc_data['document_type'],
                document_number=doc_data.get('document_number', ''),
                uploaded_file=doc_data['uploaded_file'],
                status=DocumentVerification.VerificationStatus.PENDING
            )
        
        return courier_provider


class CourierProviderLogoSerializer(serializers.ModelSerializer):
    """Serializer for courier admins to upload/update company logo."""

    logo_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CourierProvider
        fields = ['id', 'name', 'logo', 'logo_url']
        read_only_fields = ['id', 'name', 'logo_url']
        extra_kwargs = {
            'logo': {'required': False, 'allow_null': True}
        }

    def get_logo_url(self, obj):
        request = self.context.get('request')
        if not obj.logo:
            return None
        if request is None:
            return obj.logo.url
        return request.build_absolute_uri(obj.logo.url)


class CourierProviderProfileSerializer(serializers.ModelSerializer):
    """Serializer for courier provider company profile in CRM settings."""

    logo_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CourierProvider
        fields = [
            'id',
            'name',
            'logo',
            'logo_url',
            'company_email',
            'company_phone',
            'address_line',
            'city',
            'state',
            'postal_code',
            'country',
            'operational_status',
            'is_active',
            'max_riders',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'logo_url',
            'operational_status',
            'is_active',
            'max_riders',
            'updated_at',
        ]
        extra_kwargs = {
            'logo': {'required': False, 'allow_null': True},
            'name': {'required': False},
            'company_email': {'required': False},
            'company_phone': {'required': False},
            'address_line': {'required': False},
            'city': {'required': False},
            'state': {'required': False},
            'postal_code': {'required': False},
            'country': {'required': False},
        }

    def get_logo_url(self, obj):
        request = self.context.get('request')
        if not obj.logo:
            return None
        if request is None:
            return obj.logo.url
        return request.build_absolute_uri(obj.logo.url)
