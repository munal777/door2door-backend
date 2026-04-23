from django.urls import path

from notifications.views import (
    RegisterPushTokenAPIView,
    UnregisterPushTokenAPIView,
    NotificationListAPIView,
    NotificationReadAPIView,
)

urlpatterns = [
    path('push-token/', RegisterPushTokenAPIView.as_view(), name='register-push-token'),
    path('push-token/unregister/', UnregisterPushTokenAPIView.as_view(), name='unregister-push-token'),
    path('list/', NotificationListAPIView.as_view(), name='notification-list'),
    path('<str:pk>/read/', NotificationReadAPIView.as_view(), name='notification-read'),
]
