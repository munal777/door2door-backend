from django.urls import re_path

from riders.consumers import RiderOrderLocationConsumer


websocket_urlpatterns = [
    re_path(r'^ws/riders/orders/(?P<order_number>[^/]+)/location/$', RiderOrderLocationConsumer.as_asgi()),
]
