from rest_framework import status, generics
from rest_framework.permissions import AllowAny, IsAuthenticated

from myproject.utils import api_response
from myproject.permissions import IsCourierAdmin, IsCourierStaff

from accounts.models import CourierStaff

from accounts.serializers.staff import (
    CourierStaffDetailSerializer,
    CourierStaffListSerializer,
    CourierStaffRegistrationSerializer,
    CourierStaffRolePermissionUpdateSerializer,
)


class CourierStaffRegistrationView(generics.CreateAPIView):
    """
    API endpoint for courier staff registration with invitation token.
    Staff must provide a valid invitation token (for admin/operations role).
    """
    serializer_class = CourierStaffRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        """Handle staff registration"""
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                staff = serializer.save()
                return api_response(
                    result={
                        'message': 'Courier staff registration successful.'
                    },
                    is_success=True,
                    status_code=status.HTTP_201_CREATED
                )
            except Exception as e:
                return api_response(
                    error_message=f'Registration failed: {str(e)}',
                    is_success=False,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        
        return api_response(
            error_message=serializer.errors,
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class CourierStaffListAPIView(generics.ListAPIView):
    """
    List courier staff members for the authenticated courier provider.
    """

    serializer_class = CourierStaffListSerializer
    permission_classes = [IsAuthenticated, IsCourierStaff]

    def get_queryset(self):
        courier_provider = self.request.courier
        queryset = CourierStaff.objects.select_related('user', 'company').filter(company=courier_provider)

        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            if str(is_active).lower() in ['true', '1']:
                queryset = queryset.filter(is_active=True)
            elif str(is_active).lower() in ['false', '0']:
                queryset = queryset.filter(is_active=False)

        return queryset

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return api_response(result=serializer.data, is_success=True, status_code=status.HTTP_200_OK)


class CourierStaffDetailAPIView(generics.RetrieveAPIView):
    """
    Get detailed profile of a courier staff member.
    """

    serializer_class = CourierStaffDetailSerializer
    permission_classes = [IsAuthenticated, IsCourierStaff]

    def get_queryset(self):
        return CourierStaff.objects.select_related('user', 'company').filter(company=self.request.courier)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return api_response(result=serializer.data, is_success=True, status_code=status.HTTP_200_OK)


class CourierStaffRolePermissionUpdateAPIView(generics.UpdateAPIView):
    """
    Update staff role and granular permissions.
    Only courier admins can modify staff access controls.
    """

    serializer_class = CourierStaffRolePermissionUpdateSerializer
    permission_classes = [IsAuthenticated, IsCourierAdmin]

    def get_queryset(self):
        return CourierStaff.objects.select_related('user', 'company').filter(company=self.request.courier)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        # Prevent admins from accidentally locking themselves out.
        if instance.user_id == request.user.id and 'role' in request.data and request.data.get('role') != instance.role:
            return api_response(
                error_message='You cannot change your own role from this endpoint.',
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if not serializer.is_valid():
            return api_response(
                error_message=serializer.errors,
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        serializer.save()
        detail_serializer = CourierStaffDetailSerializer(instance)
        return api_response(result=detail_serializer.data, is_success=True, status_code=status.HTTP_200_OK)
