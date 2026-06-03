from rest_framework.response import Response
from rest_framework import status
from datetime import datetime


def api_response(
    result=None,
    is_success=False,
    error_message=None,
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
):
    return Response(
        {
            "StatusCode": status_code,
            "IsSuccess": is_success,
            "ErrorMessage": error_message if error_message else [],
            "Result": result,
        },
        status=status_code,
    )


def format_datetime(dt):
    """
    Format datetime to a simple
    """
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    return dt


def build_file_url(request, file_field):
    if not file_field:
        return None
    url = file_field.url
    if request and url and not url.startswith('http'):
        return request.build_absolute_uri(url)
    return url