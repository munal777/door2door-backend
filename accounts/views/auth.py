from rest_framework import status, generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView
from django.utils import timezone

from django.core.cache import cache

from myproject.utils import api_response
from accounts.serializers.auth import (
    UserRegisrationSerializer,
    LoginUserSerializer,
    ConsumerLoginSerializer,
    CourierStaffLoginSerializer,
    RiderLoginSerializer,
    AdminLoginSerializer,
    SendOTPSerializer, 
    ValidateOTPSerializer, 
    ChangePasswordSerializer,
)
from accounts.utils import generate_otp
from accounts.tasks import send_otp_email


class UserRegistrationView(generics.CreateAPIView):
    """
    API endpoint for normal user registration.    
    Allows any user to register a new account.
    """
    serializer_class = UserRegisrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            return api_response(
                result={
                    'message': 'User registered successfully. You can now login with your credentials.'
                },
                is_success=True,
                status_code=status.HTTP_201_CREATED
            )
        
        return api_response(
            error_message=serializer.errors,
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class UserLoginView(TokenObtainPairView):
    serializer_class = LoginUserSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return api_response(
            error_message=serializer.errors,
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST
        )

        return api_response(
            result=serializer.validated_data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )
    
class ConsumerLoginView(UserLoginView):
    serializer_class = ConsumerLoginSerializer

class CourierStaffLoginView(UserLoginView):
    serializer_class = CourierStaffLoginSerializer

class RiderLoginView(UserLoginView):
    serializer_class = RiderLoginSerializer

class AdminLoginView(UserLoginView):
    serializer_class = AdminLoginSerializer




class SendOTPView(generics.CreateAPIView):
    serializer_class = SendOTPSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            email = serializer.validated_data['email']
            otp_code = generate_otp()
            cache.set(f"otp:{email}", otp_code, timeout=300)
            send_otp_email.delay(email, otp_code)

            return api_response(
                result={"message": "OTP sent to email"},
                is_success=True,
                status_code=status.HTTP_200_OK
            )

        return api_response(
            error_message=serializer.errors,
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST
        )




class ValidateOTPView(generics.CreateAPIView):
    serializer_class = ValidateOTPSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            return api_response(
                result={"message": "OTP verified successfully."},
                is_success=True,
                status_code=status.HTTP_200_OK
            )

        return api_response(
            error_message=serializer.errors,
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST
        )




class ChangePasswordAPIView(generics.CreateAPIView):

    serializer_class = ChangePasswordSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()

            return api_response(
                result={"message": "Password changed successfully."},
                is_success=True,
                status_code=status.HTTP_200_OK
            )

        return api_response(
            error_message=serializer.errors,
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST
        )