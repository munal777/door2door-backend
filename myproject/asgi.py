import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

django_asgi_app = get_asgi_application()

from myproject.routing import websocket_urlpatterns
from myproject.websocket_auth import JWTAuthMiddlewareStack

application = ProtocolTypeRouter(
	{
		'http': django_asgi_app,
		'websocket': JWTAuthMiddlewareStack(
			URLRouter(websocket_urlpatterns)
		),
	}
)
