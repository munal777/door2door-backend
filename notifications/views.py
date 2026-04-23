from rest_framework import generics, permissions, status
from django.utils import timezone

from myproject.utils import api_response
from notifications.models import UserPushToken, Notification
from notifications.serializers import TokenRegisterSerializer, NotificationSerializer


class RegisterPushTokenAPIView(generics.CreateAPIView):
    serializer_class = TokenRegisterSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return api_response(
                error_message=serializer.errors,
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        token = serializer.validated_data['token']
        platform = serializer.validated_data['platform']

        UserPushToken.objects.update_or_create(
            token=token,
            defaults={
                'user': request.user,
                'platform': platform,
                'is_active': True,
                'last_used_at': timezone.now(),
            },
        )

        return api_response(
            result={'message': 'Push token registered successfully.'},
            is_success=True,
            status_code=status.HTTP_200_OK,
        )


class UnregisterPushTokenAPIView(generics.GenericAPIView):
    """
    API endpoint to deactivate push tokens on logout.
    Marks all active tokens for the current user as inactive.
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        # Deactivate all active tokens for the current user
        updated_count = UserPushToken.objects.filter(
            user=request.user,
            is_active=True
        ).update(is_active=False)

        return api_response(
            result={
                'message': 'Push token(s) unregistered successfully.',
                'tokens_deactivated': updated_count
            },
            is_success=True,
            status_code=status.HTTP_200_OK,
        )


class NotificationListAPIView(generics.ListAPIView):
    """
    List user notifications.
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
        
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        # Pagination not implemented explicitly but you can add it if needed.
        # For now return via unified api_response.
        serializer = self.get_serializer(queryset[:50], many=True)
        return api_response(result=serializer.data, is_success=True, status_code=status.HTTP_200_OK)


class NotificationReadAPIView(generics.GenericAPIView):
    """
    Mark a specific notification as read, or pass 'all' to mark all.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        if str(pk).lower() == 'all':
            Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
            return api_response(result={'message': 'All notifications marked as read.'}, is_success=True, status_code=status.HTTP_200_OK)
        
        try:
            notif = Notification.objects.get(pk=pk, user=request.user)
            notif.is_read = True
            notif.save(update_fields=['is_read'])
            return api_response(result={'message': 'Notification marked as read.'}, is_success=True, status_code=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return api_response(
                error_message='Notification not found.',
                is_success=False,
                status_code=status.HTTP_404_NOT_FOUND
            )
