from rest_framework import status, generics
from django.shortcuts import get_object_or_404

from myproject.permissions import IsSystemAdmin
from myproject.utils import api_response

from accounts.models import CourierProvider, Rider
from accounts.serializers.admin import (
    CourierProviderApprovalSerializer,
    CourierProviderDetailSerializer,
    CourierRiderApprovalSerializer,
    RiderAdminDetailSerializer
)


class ApproveCourierProviderView(generics.CreateAPIView):
    """
    API endpoint for admin to approve/reject courier provider registration.
    """
    permission_classes = [IsSystemAdmin]
    serializer_class = CourierProviderApprovalSerializer

    def create(self, request, *args, **kwargs):
        provider_id = self.kwargs.get('provider_id')
        courier_provider = get_object_or_404(CourierProvider, id=provider_id)
        
        # Check if provider is in correct status
        if courier_provider.operational_status not in [
            CourierProvider.OperationalStatus.UNDER_REVIEW,
            CourierProvider.OperationalStatus.PENDING_DOCUMENTS
        ]:
            return api_response(
                error_message=f'Cannot process provider with status: {courier_provider.operational_status}',
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            return api_response(
                error_message=serializer.errors,
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        action = serializer.validated_data['action']
        
        try:
            if action == 'approve':
                result = serializer.approve_provider(courier_provider, request.user)
                provider = result['courier_provider']
                admin = result['admin_user']
                
                return api_response(
                    result={
                        'provider_id': provider.id,
                        'provider_name': provider.name,
                        'company_email': provider.company_email,
                        'admin_email': admin.email,
                        'operational_status': provider.operational_status,
                        'message': result['message']
                    },
                    is_success=True,
                    status_code=status.HTTP_200_OK
                )
            
            elif action == 'reject':
                rejection_reason = serializer.validated_data.get('rejection_reason', '')
                result = serializer.reject_provider(courier_provider, request.user, rejection_reason)
                provider = result['courier_provider']
                
                return api_response(
                    result={
                        'provider_id': provider.id,
                        'provider_name': provider.name,
                        'company_email': provider.company_email,
                        'operational_status': provider.operational_status,
                        'rejection_reason': rejection_reason,
                        'message': result['message']
                    },
                    is_success=True,
                    status_code=status.HTTP_200_OK
                )
        
        except Exception as e:
            return api_response(
                error_message=f'An error occurred: {str(e)}',
                is_success=False,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CourierProviderListView(generics.ListAPIView):
    """
    API endpoint to list all courier providers (Admin only)
    """
    serializer_class = CourierProviderDetailSerializer
    permission_classes = [IsSystemAdmin]
    
    def get_queryset(self):
        queryset = CourierProvider.objects.all()
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(operational_status=status_filter)
        
        return queryset.order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )


class CourierProviderDetailView(generics.RetrieveAPIView):
    """
    API endpoint to get courier provider details (Admin only)
    """
    serializer_class = CourierProviderDetailSerializer
    permission_classes = [IsSystemAdmin]
    queryset = CourierProvider.objects.all()

    def get_object(self):
        queryset = self.get_queryset()
        provider_id = self.kwargs.get("pk")
        obj = get_object_or_404(queryset, id=provider_id)
        self.check_object_permissions(self.request, obj)
        return obj

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )


# Admin rider APIViews
class ApproveCourierRiderView(generics.CreateAPIView):
    """
    API endpoint for admin to approve/reject courier rider registration.
    """
    permission_classes = [IsSystemAdmin]
    serializer_class = CourierRiderApprovalSerializer

    def create(self, request, *args, **kwargs):
        rider_id = self.kwargs.get('rider_id')
        rider = get_object_or_404(Rider, id=rider_id)
        
        # Check if rider is in correct status
        if rider.operational_status not in [
            Rider.OperationalStatus.UNDER_REVIEW,
            Rider.OperationalStatus.PENDING_DOCUMENTS
        ]:
            return api_response(
                error_message=f'Cannot process rider with status: {rider.operational_status}',
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            return api_response(
                error_message=serializer.errors,
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        action = serializer.validated_data['action']
        
        try:
            if action == 'approve':
                result = serializer.approve_rider(rider, request.user)
                rider_obj = result['rider']
                
                return api_response(
                    result={
                        'rider_id': rider_obj.id,
                        'rider_name': f"{rider_obj.user.first_name} {rider_obj.user.last_name}",
                        'email': rider_obj.user.email,
                        'operational_status': rider_obj.operational_status,
                        'message': result['message']
                    },
                    is_success=True,
                    status_code=status.HTTP_200_OK
                )
            
            elif action == 'reject':
                rejection_reason = serializer.validated_data.get('rejection_reason', '')
                result = serializer.reject_rider(rider, request.user, rejection_reason)
                rider_obj = result['rider']
                
                return api_response(
                    result={
                        'rider_id': rider_obj.id,
                        'rider_name': f"{rider_obj.user.first_name} {rider_obj.user.last_name}",
                        'email': rider_obj.user.email,
                        'operational_status': rider_obj.operational_status,
                        'rejection_reason': rejection_reason,
                        'message': result['message']
                    },
                    is_success=True,
                    status_code=status.HTTP_200_OK
                )
        
        except Exception as e:
            return api_response(
                error_message=f'An error occurred: {str(e)}',
                is_success=False,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        


class RiderListView(generics.ListAPIView):
    """
    API endpoint to list all courier riders (Admin only)
    """
    serializer_class = RiderAdminDetailSerializer
    permission_classes = [IsSystemAdmin]
    
    def get_queryset(self):
        queryset = Rider.objects.select_related('user', 'company').all()
        
        # Filter by operational status if provided
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(operational_status=status_filter)
        
        # Filter by company if provided
        company_id = self.request.query_params.get('company_id', None)
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        
        # Filter by availability status if provided
        availability_filter = self.request.query_params.get('availability', None)
        if availability_filter:
            queryset = queryset.filter(availability_status=availability_filter)
        
        return queryset.order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )


class RiderDetailView(generics.RetrieveAPIView):
    """
    API endpoint to get courier rider details (Admin only)
    """
    serializer_class = RiderAdminDetailSerializer
    permission_classes = [IsSystemAdmin]
    queryset = Rider.objects.select_related('user', 'company').all()

    def get_object(self):
        queryset = self.get_queryset()
        rider_id = self.kwargs.get("pk")
        obj = get_object_or_404(queryset, id=rider_id)
        self.check_object_permissions(self.request, obj)
        return obj

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )

