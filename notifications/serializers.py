from rest_framework import serializers

from notifications.models import UserPushToken


class TokenRegisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255)
    platform = serializers.ChoiceField(
        choices=UserPushToken.Platform.choices,
        default=UserPushToken.Platform.UNKNOWN,
    )

    def validate_token(self, value):
        token = value.strip()
        if not token:
            raise serializers.ValidationError('Push token is required.')
        return token


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        from notifications.models import Notification
        model = Notification
        fields = [
            'id',
            'title',
            'body',
            'data',
            'is_read',
            'created_at',
        ]
        read_only_fields = fields