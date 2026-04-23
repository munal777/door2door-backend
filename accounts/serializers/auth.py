import re
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.cache import cache
from django.contrib.auth import get_user_model

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile information.
    Used for displaying user data in responses.
    """
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'user_type',
            'is_active',
            'is_verified',
        ]
        read_only_fields = [
            'id',
            'email',
            'user_type',
            'is_active',
            'is_verified',
        ]


class UserRegisrationSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 'password', 'confirm_password']
        read_only_fields = ['id']
        extra_kwargs = {
            'password': {'write_only': True, 'required': True}
        }

    def validate_email(self, value):
        """
        Validate email format and uniqueness.
        """
        # Check if email already exists (case-insensitive)
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        
        # Additional email format validation
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, value):
            raise serializers.ValidationError("Enter a valid email address.")
        
        return value.lower()  # Store email in lowercase

    def validate_first_name(self, value):
        """
        Validate first name contains only letters and spaces (for middle names).
        """
        if not value:
            return value
        
        # Check for valid characters (only letters and spaces)
        if not re.match(r'^[a-zA-Z\s]+$', value):
            raise serializers.ValidationError(
                "First name should only contain letters and spaces."
            )
        
        # Check length
        if len(value.strip()) < 2:
            raise serializers.ValidationError("First name must be at least 2 characters long.")
        
        return value.strip().title()  # Capitalize properly

    def validate_last_name(self, value):
        """
        Validate last name contains only letters (no spaces or special characters).
        """
        if not value:
            return value
        
        # Check for valid characters (only letters, no spaces or special characters)
        if not re.match(r'^[a-zA-Z]+$', value):
            raise serializers.ValidationError(
                "Last name should only contain letters."
            )
        
        # Check length
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Last name must be at least 2 characters long.")
        
        return value.strip().title()  # Capitalize properly

    def validate_phone_number(self, value):
        """
        Validate phone number format for Nepal.
        Accepts formats: +9779XXXXXXXXX, 9XXXXXXXXX, or 09XXXXXXXXX
        Stores only the 10-digit number without country code or leading zero.
        """
        if not value:
            return value
        
        # Remove spaces, hyphens, and parentheses for validation
        cleaned_number = re.sub(r'[\s\-\(\)]', '', value)
        
        # Remove +977 country code if present
        if cleaned_number.startswith('+977'):
            cleaned_number = cleaned_number[4:]  # Remove '+977'
        
        # Validate that we have exactly 10 digits
        if not re.match(r'^\d{10}$', cleaned_number):
            raise serializers.ValidationError(
                "Enter a valid Nepal phone number with 10 digits."
            )
        
        # Validate mobile numbers (should start with 96, 97, 98, 99)
        if not re.match(r'^[96-9]\d{9}$', cleaned_number):
            raise serializers.ValidationError(
                "Enter a valid Nepal mobile number."
            )
        
        # Check if phone number already exists
        if User.objects.filter(phone_number=cleaned_number).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        
        return cleaned_number

    def validate_password(self, value):
        """
        Validate password strength using Django's built-in validators.
        """
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        
        # Additional custom validation
        if not re.search(r'\d', value):
            raise serializers.ValidationError("Password must contain at least one digit.")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        
        return value

    def validate(self, attrs):
        """
        Validate that password and confirm_password match.
        """
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        
        if password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        
        return attrs

    def create(self, validated_data):
        """
        Create and return a new user instance with hashed password.
        """
        # Remove confirm_password as it's not needed after validation
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password')
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        return user

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    

class LoginUserSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        try:
            data = super().validate(attrs)    
        except AuthenticationFailed:
            raise serializers.ValidationError(
                {"detail": "Invalid email or password"}
            )
        
        user_data = UserProfileSerializer(self.user).data

        data.update({
            "user": user_data
        })

        return data
    

class ConsumerLoginSerializer(LoginUserSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.user_type != User.UserType.CONSUMER:
            raise serializers.ValidationError({"detail": "Invalid credentials. This account does not have consumer access."})
        return data

class CourierStaffLoginSerializer(LoginUserSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.user_type != User.UserType.COURIER_STAFF:
            raise serializers.ValidationError({"detail": "Invalid credentials. This account does not have courier staff access."})

        # Convert ReturnDict to a plain dict so we can freely extend it
        user_data = dict(data['user'])

        try:
            staff = self.user.courier_staff_profile
            user_data['role'] = staff.role
            user_data['permissions'] = {
                'can_manage_orders':      staff.is_admin or staff.can_manage_orders,
                'can_manage_shippings':   staff.is_admin or staff.can_manage_shippings,
                'can_manage_riders': staff.is_admin or staff.can_manage_riders,
                'can_manage_invitations': staff.is_admin or staff.can_manage_invitations,
                'can_manage_settings':    staff.is_admin or staff.can_manage_settings,
            }
        except Exception as e:
            raise serializers.ValidationError({"detail": f"Staff profile error: {str(e)}"})

        data['user'] = user_data
        return data

class RiderLoginSerializer(LoginUserSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.user_type != User.UserType.RIDER:
            raise serializers.ValidationError({"detail": "Invalid credentials. This account does not have rider access."})
        return data

class AdminLoginSerializer(LoginUserSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.user_type not in [User.UserType.SYSTEM_ADMIN, User.UserType.SYSTEM_SUPER_ADMIN]:
            raise serializers.ValidationError({"detail": "Invalid credentials. This account does not have admin access."})
        return data


class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, attrs):
        email = attrs.get('email', '')
        if not User.objects.filter(email= email).exists():
            raise serializers.ValidationError("No account exist with this email.")

        return attrs        



class ValidateOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField()

    def validate(self, attrs):
        email = attrs.get("email")
        otp = attrs.get("otp")

        key= f"otp:{email}"
        stored_otp = cache.get(key)

        if stored_otp is None:
            raise serializers.ValidationError("OTP has expired or was not found.")
        
        if stored_otp != otp:
            raise serializers.ValidationError("Invalid OTP.")
        
        # OTP is valid, now mark as verified
        cache.delete(key)
        cache.set(f"otp_verified:{email}", True, timeout=300)
        
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        """
        Validate password strength using Django's built-in validators.
        """
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        
        return value

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        confirm_password = attrs.get("confirm_password")
        verified_key = f"otp_verified:{email}"

        # Check if passwords match
        if password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        if not cache.get(verified_key):
            raise serializers.ValidationError("OTP not verified or expired.")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")

        if user.check_password(password):
            raise serializers.ValidationError("New password can’t be the same as the old one.")

        attrs["user"] = user

        return attrs
    

    def save(self):
        user = self.validated_data["user"]
        new_password = self.validated_data["password"]

        verified_key = f"otp_verified:{user.email}"

        user.set_password(new_password)
        user.save()

        cache.delete(verified_key)