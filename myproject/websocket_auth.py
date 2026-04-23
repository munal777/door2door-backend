from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication


@database_sync_to_async
def _get_user_for_token(raw_token: str):
    jwt_auth = JWTAuthentication()
    validated_token = jwt_auth.get_validated_token(raw_token)
    return jwt_auth.get_user(validated_token)


class JWTAuthMiddleware(BaseMiddleware):
    """
    Channels middleware that authenticates websocket connections using JWT.
    """

    async def __call__(self, scope, receive, send):
        scope['user'] = None

        try:
            token = None
            query_string = scope.get('query_string', b'').decode()
            query_params = parse_qs(query_string)
            if 'token' in query_params and query_params['token']:
                token = query_params['token'][0]

            if not token:
                headers = dict(scope.get('headers', []))
                auth_header = headers.get(b'authorization')
                if auth_header:
                    auth_value = auth_header.decode()
                    if auth_value.lower().startswith('bearer '):
                        token = auth_value.split(' ', 1)[1].strip()

            if token:
                scope['user'] = await _get_user_for_token(token)
        except Exception:
            scope['user'] = None

        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
