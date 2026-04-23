from rest_framework import serializers

from accounts.models import User

class ConsumerProfileSerializer(serializers.ModelSerializer):
    """Serializer for updating consumer profile details."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number']

    def validate_phone_number(self, value):
        phone = value.strip()
        if phone and not phone.isdigit():
            raise serializers.ValidationError('Phone number must contain only digits.')
        return phone
