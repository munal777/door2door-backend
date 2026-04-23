# payments/signature.py
import uuid
import hmac
import hashlib
import base64

from typing import Mapping, Sequence

def build_signed_string_from_fields(field_names: Sequence[str], data: Mapping[str, str], sep: str = ",") -> str:
    """
    Build the eSewa signing string in the format:
      name1=value1,name2=value2,...
    using the provided field_names order and values from data.
    """
    parts = []
    for name in field_names:
        if name not in data:
            # Use empty string if a field is missing, or raise depending on your policy
            value = ""
        else:
            value = str(data[name])
        parts.append(f"{name}={value}")
    return sep.join(parts)


def generate_esewa_signature(key, message):
    key = key.encode('utf-8')
    message = message.encode('utf-8')

    hmac_sha256 = hmac.new(key, message, hashlib.sha256)
    digest = hmac_sha256.digest()

    #Convert the digest to a Base64-encoded string
    signature = base64.b64encode(digest).decode('utf-8')

    return signature


def generate_transaction_uuid():
    """
    Generate a unique transaction UUID for eSewa payment.
    Uses only alphanumeric characters and hyphens.
    """
    return str(uuid.uuid4())