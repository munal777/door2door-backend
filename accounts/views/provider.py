from rest_framework import status, generics, permissions
from rest_framework.exceptions import NotFound

from myproject.utils import api_response
from myproject.permissions import (
    CanViewOrManageCourierSettings,
    IsCourierAdmin,
)

from accounts.models.provider import CourierProvider
from accounts.parsers import NestedMultipartParser
from accounts.serializers.provider import (
    CourierProviderProfileSerializer,
    CourierProviderRegistrationSerializer,
    CourierProviderLogoSerializer,
)


class CourierProviderRegistrationView(generics.CreateAPIView):
    """
    API endpoint for courier provider registration.
    """
    serializer_class = CourierProviderRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    parser_classes = [NestedMultipartParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            
            return api_response(
                result={
                    'message': 'Courier provider registration submitted successfully. '
                              'Your application is under review. You will receive an email '
                              'with login credentials once approved.'
                },
                is_success=True,
                status_code=status.HTTP_201_CREATED
            )
        
        return api_response(
            error_message=serializer.errors,
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class CourierProviderMeLogoView(generics.RetrieveUpdateAPIView):
    """Courier-admin endpoint to view/update their company's logo."""

    serializer_class = CourierProviderLogoSerializer
    permission_classes = [IsCourierAdmin]
    parser_classes = [NestedMultipartParser]

    def get_object(self):
        # request.courier is populated by JWTAuthenticationWithCourier
        courier = self.request.courier
        if not courier:
            raise NotFound('Courier provider not found for this user.')
        return courier

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        partial = kwargs.pop('partial', True)

        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        if not serializer.is_valid():
            return api_response(
                error_message=serializer.errors,
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        serializer.save()

        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )


class CourierProviderProfileView(generics.RetrieveUpdateAPIView):
    """Courier staff endpoint to view/update their company profile."""

    serializer_class = CourierProviderProfileSerializer
    permission_classes = [permissions.IsAuthenticated, CanViewOrManageCourierSettings]
    parser_classes = [NestedMultipartParser]

    def get_object(self):
        courier = self.request.courier
        if not courier:
            raise NotFound('Courier provider not found for this user.')
        return courier

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        partial = kwargs.pop('partial', True)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        if not serializer.is_valid():
            return api_response(
                error_message=serializer.errors,
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        serializer.save()
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )
