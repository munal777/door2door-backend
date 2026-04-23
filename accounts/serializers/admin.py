from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string
from rest_framework import serializers

from accounts.models import CourierProvider, CourierStaff, DocumentVerification, User, Rider
from accounts.tasks import send_approval_email, send_rejection_email
from myproject.utils import format_datetime


class CourierProviderApprovalSerializer(serializers.Serializer):
    """
    Serializer for admin to approve/reject courier provider registration.
    """
    
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Ensure rejection reason is provided when rejecting"""
        if data['action'] == 'reject' and not data.get('rejection_reason'):
            raise serializers.ValidationError({
                'rejection_reason': 'Rejection reason is required when rejecting.'
            })
        return data

    @transaction.atomic
    def approve_provider(self, courier_provider, admin_user):
        
        # Update all pending documents to approved
        courier_provider.documents.filter(
            status=DocumentVerification.VerificationStatus.PENDING
        ).update(
            status=DocumentVerification.VerificationStatus.APPROVED,
            verified_by=admin_user,
            verified_at=timezone.now()
        )
        
        # Update operational status
        courier_provider.operational_status = CourierProvider.OperationalStatus.ACTIVE
        courier_provider.save()
        
        # Create admin user account for courier
        password = get_random_string(12)  # Generate secure random password
        
        courier_admin = User.objects.create_user(
            email=courier_provider.company_email,
            password=password,
            first_name=courier_provider.name,
            last_name='Admin',
            phone_number=courier_provider.company_phone,
            user_type=User.UserType.COURIER_STAFF,
            is_active=True,
            is_verified=True
        )
        
        # Create CourierStaff profile with ADMIN role
        CourierStaff.objects.create(
            user=courier_admin,
            company=courier_provider,
            role=CourierStaff.StaffRole.ADMIN,
            can_manage_riders=True,
            can_manage_invitations=True,
            can_manage_orders=True,
            can_manage_shippings=True,
            can_manage_settings=True,
        )
        
        # Send credentials via email
        send_approval_email.delay(courier_provider.id, courier_admin.email, password)
        
        return {
            'courier_provider': courier_provider,
            'admin_user': courier_admin,
            'message': 'Courier provider approved successfully. Credentials sent via email.'
        }

    @transaction.atomic
    def reject_provider(self, courier_provider, admin_user, rejection_reason):

        # Update all pending documents to rejected
        courier_provider.documents.filter(
            status=DocumentVerification.VerificationStatus.PENDING
        ).update(
            status=DocumentVerification.VerificationStatus.REJECTED,
            verified_by=admin_user,
            verified_at=timezone.now(),
            rejection_reason=rejection_reason
        )
        
        # Update operational status
        courier_provider.operational_status = CourierProvider.OperationalStatus.SUSPENDED
        courier_provider.save()
        
        # Send rejection email
        send_rejection_email.delay(courier_provider.id, rejection_reason)
        
        return {
            'courier_provider': courier_provider,
            'message': 'Courier provider registration rejected. Notification sent.'
        }


class CourierProviderDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for courier provider with document information"""
    
    documents = serializers.SerializerMethodField()
    is_verified = serializers.ReadOnlyField()
    total_riders = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()
    
    class Meta:
        model = CourierProvider
        fields = [
            'id',
            'name',
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
            'is_verified',
            'max_riders',
            'total_riders',
            'documents',
            'created_at',
            'updated_at',
        ]

    def get_logo_url(self, obj):
        request = self.context.get('request')
        if not getattr(obj, 'logo', None):
            return None
        if request is None:
            return obj.logo.url
        return request.build_absolute_uri(obj.logo.url)
    
    def get_documents(self, obj):
        """Get all documents with their verification status"""
        documents = obj.documents.all()
        return [{
            'id': doc.id,
            'document_type': doc.document_type,
            'document_number': doc.document_number,
            'uploaded_file': self.context.get('request').build_absolute_uri(doc.uploaded_file.url) if doc.uploaded_file else None,
            'status': doc.status,
            'uploaded_at': format_datetime(doc.uploaded_at),
            'verified_at': format_datetime(doc.verified_at),
            'rejection_reason': doc.rejection_reason if doc.status == 'rejected' else None,
        } for doc in documents]
    
    def get_total_riders(self, obj):
        """Get total number of riders associated with this provider"""
        return obj.riders.count() if hasattr(obj, 'riders') else 0
    
    def get_created_at(self, obj):
        """Format created_at to simple datetime"""
        return format_datetime(obj.created_at)
    
    def get_updated_at(self, obj):
        """Format updated_at to simple datetime"""
        return format_datetime(obj.updated_at)


# Admin works for Rider serializers
class CourierRiderApprovalSerializer(serializers.Serializer):
    """
    Serializer for admin to approve/reject courier rider registration.
    """
    
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        """Ensure rejection reason is provided when rejecting"""
        if data['action'] == 'reject' and not data.get('rejection_reason'):
            raise serializers.ValidationError({
                'rejection_reason': 'Rejection reason is required when rejecting.'
            })
        return data

    @transaction.atomic
    def approve_rider(self, rider, admin_user):

        # Update all pending documents to approved
        rider.documents.filter(
            status=DocumentVerification.VerificationStatus.PENDING
        ).update(
            status=DocumentVerification.VerificationStatus.APPROVED,
            verified_by=admin_user,
            verified_at=timezone.now()
        )

        # Update operational status
        rider.operational_status = Rider.OperationalStatus.ACTIVE
        rider.save()

        return {
            'rider': rider,
            'message': 'Courier Rider registration approved successfully.',
        }

    @transaction.atomic
    def reject_rider(self, rider, admin_user, rejection_reason):
        
         # Update all pending documents to rejected
        rider.documents.filter(
            status=DocumentVerification.VerificationStatus.PENDING
        ).update(
            status=DocumentVerification.VerificationStatus.REJECTED,
            verified_by=admin_user,
            verified_at=timezone.now(),
            rejection_reason=rejection_reason
        )

        # Update operational status
        rider.operational_status = Rider.OperationalStatus.SUSPENDED
        rider.save()

        return {
            'rider': rider,
            'message': 'Courier Rider registration rejected.',
        }


class RiderAdminDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for courier rider with document information (Admin view)"""
    
    documents = serializers.SerializerMethodField()
    user_details = serializers.SerializerMethodField()
    company_details = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()
    
    class Meta:
        model = Rider
        fields = [
            'id',
            'user_details',
            'company_details',
            'date_of_birth',
            'emergency_contact_name',
            'emergency_contact_phone',
            'vehicle_type',
            'vehicle_number',
            'vehicle_model',
            'vehicle_color',
            'operational_status',
            'documents',
            'created_at',
            'updated_at',
        ]
    
    def get_user_details(self, obj):
        """Get user information"""
        return {
            'id': obj.user.id,
            'email': obj.user.email,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name,
            'full_name': f"{obj.user.first_name} {obj.user.last_name}",
            'phone_number': obj.user.phone_number,
            'is_active': obj.user.is_active,
        }
    
    def get_company_details(self, obj):
        """Get company information"""
        return {
            'id': obj.company.id,
            'name': obj.company.name,
            'company_email': obj.company.company_email,
            'company_phone': obj.company.company_phone,
        }
    
    def get_documents(self, obj):
        """Get all documents with their verification status"""
        documents = obj.documents.all()
        return [{
            'id': doc.id,
            'document_type': doc.document_type,
            'document_number': doc.document_number,
            'uploaded_file': self.context.get('request').build_absolute_uri(doc.uploaded_file.url) if doc.uploaded_file else None,
            'status': doc.status,
            'uploaded_at': format_datetime(doc.uploaded_at),
            'verified_at': format_datetime(doc.verified_at),
            'rejection_reason': doc.rejection_reason if doc.status == 'rejected' else None,
        } for doc in documents]
    
    def get_created_at(self, obj):
        """Format created_at to simple datetime"""
        return format_datetime(obj.created_at)
    
    def get_updated_at(self, obj):
        """Format updated_at to simple datetime"""
        return format_datetime(obj.updated_at)

