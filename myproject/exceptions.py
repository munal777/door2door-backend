from rest_framework.views import exception_handler
from rest_framework.response import Response

def custom_exception_handler(exc, context):

    response = exception_handler(exc, context)


    if response is not None:

        # Extract code and message
        code = getattr(exc, "default_code", "error")
        
        # Handle different response data formats
        if isinstance(response.data, dict):
            # If there's a "detail" key, use it directly
            if "detail" in response.data:
                message = response.data["detail"]
            else:
                # For ValidationError with field-specific errors, extract clean messages
                message = {}
                for key, value in response.data.items():
                    if isinstance(value, list):
                        # Extract string from ErrorDetail objects in list
                        message[key] = [str(item) for item in value]
                    else:
                        # Extract string from single ErrorDetail object
                        message[key] = str(value)
        elif isinstance(response.data, list):
            message = [str(item) for item in response.data]
        else:
            message = str(response.data)
            
        print("🔎 Exception Debug:", {
            "exc": str(exc),
            "context": context,
            "status_code": response.status_code,
            "raw_response_data": response.data,
            "parsed_message": message,
        })

        return Response({
            "StatusCode": response.status_code,
            "IsSuccess": False,
            "ErrorMessage": message,
            "Result": None,
        }, status= response.status_code)